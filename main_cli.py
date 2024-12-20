from pathlib import Path
import subprocess
import argparse
import requests
import tempfile
import zipfile
import json
import time
import shutil
import os

class VCRedistManager:
    def __init__(self, base_dir: str, args):
        # Initialize the VCRedistManager with the base directory and command-line arguments
        self.project_dir = Path(__file__).parent
        self.base_dir = Path(base_dir)
        
        # Define directories for downloads, core tools, and temporary files
        self.download_dir = self.project_dir / 'downloads'
        self.core_dir = self.project_dir / 'core'
        self.tmp_dir = self.project_dir / 'tmp'
        
        # Load configuration files for vcredists and tools
        self.config = self._load_config('vcredists.json')
        self.tools = self._load_config('tools.json')
        
        # Create necessary directories unless cleanup is requested
        if not args.clean_up:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            self.download_dir.mkdir(parents=True, exist_ok=True)
            self.core_dir.mkdir(parents=True, exist_ok=True)
            self.tmp_dir.mkdir(parents=True, exist_ok=True)

        self.args = args  # Store command-line arguments for later use

    def _load_config(self, filename: str) -> dict:
        # Load a JSON configuration file and return its contents as a dictionary
        config_path = Path(__file__).parent / filename
        with open(config_path, 'r') as f:
            return json.load(f)

    def download_file(self, uri: str, dest: Path, max_retries: int = 3) -> Path:
        # Download a file from a given URI to a specified destination
        if dest.is_file():
            if not self.args.silent:
                print(f"File {dest} already exists, skipping download.")
            return dest
        
        if not self.args.silent:
            print(f"Downloading {uri} to {dest}")
        
        for attempt in range(max_retries):
            try:
                session = requests.Session()
                session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
                
                r = session.get(uri, stream=True, timeout=30)
                r.raise_for_status()
                
                with open(dest, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                if not self.args.silent:
                    print(f"Downloaded {dest}")
                return dest
                
            except (requests.exceptions.RequestException, ConnectionError) as e:
                if attempt == max_retries - 1:
                    if not self.args.silent:
                        print(f"Failed to download after {max_retries} attempts: {uri}")
                        print(f"Error: {str(e)}")
                    raise
                else:
                    if not self.args.silent:
                        print(f"Attempt {attempt + 1} failed, retrying...")
                    time.sleep(2 * (attempt + 1))

    def fetch_7zip(self) -> Path:
        # Fetch the 7-Zip executable and its extra tools
        tools_path = self.core_dir / '7zip'
        tools_path.mkdir(exist_ok=True)
        
        exe_path = tools_path / '7zr.exe'
        if not exe_path.is_file():
            self.download_file(self.tools['7zip']['7zr'], exe_path)

        tool_archive = tools_path / '7z-extra.7z'
        if not tool_archive.is_file():
            self.download_file(self.tools['7zip']['7z_extra'], tool_archive)

        seven_za = tools_path / '7za.exe'
        if not seven_za.is_file():
            subprocess.run([str(exe_path), "x", str(tool_archive), f'-o{tools_path}', '-aoa'], check=True)
        
        return seven_za

    def fetch_wix(self) -> Path:
        # Download and extract the WiX toolset for creating installers
        wix_path = self.core_dir / 'wix'
        zip_path = wix_path / 'wix.zip'
        
        if not (wix_path / 'dark.exe').is_file():
            wix_path.mkdir(exist_ok=True)
            if not self.args.silent:
                print(f"Downloading WiX toolset from {self.tools['wix']['url']} to {zip_path}")
            self.download_file(self.tools['wix']['url'], zip_path)
            
            if not self.args.silent:
                print(f"Extracting WiX toolset to {wix_path}")
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                zip_file.extractall(wix_path)
                
            zip_path.unlink()  # Remove the zip file after extraction
            
        return wix_path

    def extract_burn_bundle(self, wix_dir: Path, bundle_exe: Path) -> Path:
        # Use the WiX tool to extract a burn bundle installer
        output_dir = Path(tempfile.mkdtemp(dir=self.tmp_dir))
        if not self.args.silent:
            print(f"Extracting {bundle_exe} using WiX to {output_dir}")
        
        if self.args.silent:
            with open(os.devnull, 'w') as devnull:
                subprocess.run([str(wix_dir / 'dark.exe'), "-nologo", "-x", str(output_dir), str(bundle_exe)],
                               check=True, stdout=devnull, stderr=devnull)
        else:
            subprocess.run([str(wix_dir / 'dark.exe'), "-nologo", "-x", str(output_dir), str(bundle_exe)],
                           check=True)
        
        if not self.args.silent:
            print(f"Extraction complete: {output_dir}")
        return output_dir

    def extract_old_installer(self, seven_zip_exe: Path, installer: Path) -> Path:
        # Extract files from an old installer using 7-Zip
        output_dir = Path(tempfile.mkdtemp(dir=self.tmp_dir))
        if not self.args.silent:
            print(f"Extracting {installer} using 7-Zip to {output_dir}")
        
        if self.args.silent:
            with open(os.devnull, 'w') as devnull:
                subprocess.run([str(seven_zip_exe), "x", f'-o{output_dir}', str(installer), '-i!*.cab'],
                               check=True, stdout=devnull, stderr=devnull)
        else:
            subprocess.run([str(seven_zip_exe), "x", f'-o{output_dir}', str(installer), '-i!*.cab'],
                           check=True)
        
        if not any(output_dir.iterdir()):
            raise ValueError(f'Failed to extract any cabinet file from {installer}')
        
        return output_dir

    def find_cabs(self, directory: Path) -> list:
        # Locate all cabinet files in the specified directory
        base_path = directory / 'AttachedContainer' / 'packages'
        return [p / 'cab1.cab' for p in base_path.glob('*_amd64')]

    def extract_cab(self, cab_source: Path, destination: Path):
        # Extract the contents of a cabinet file to a specified destination
        if not self.args.silent:
            print(f"Extracting {cab_source} to {destination}")
        if self.args.silent:
            with open(os.devnull, 'w') as devnull:
                subprocess.run(['expand.exe', "-F:*", str(cab_source), str(destination)],
                               check=True, stdout=devnull, stderr=devnull)
        else:
            subprocess.run(['expand.exe', "-F:*", str(cab_source), str(destination)],
                           check=True)

    def cleanup_dlls(self, directory: Path):
        # Rename DLL files by removing the '_amd64' suffix
        for dll_file in directory.glob('*.dll_amd64'):
            new_name = dll_file.stem.replace('_amd64', '') + '.dll'
            if self.args.verbose and not self.args.silent:
                print(f"Renaming {dll_file} to {new_name}")
            dll_file.rename(directory / new_name)

    def process_runtime(self, runtime: dict, include_old_versions: bool = False) -> None:
        # Process a specific runtime version, downloading and extracting as necessary
        version = runtime['version']
        major_version = int(version.split('.')[0])
        
        if not include_old_versions and major_version < 14:
            return  # Skip older versions if not included

        output_dir = self.base_dir / f'vcruntime_{version}'.lower()
        if output_dir.exists() and any(output_dir.iterdir()):
            if not self.args.silent:
                print(f'Already have {version}')
            return  # Skip if the version is already processed

        output_dir.mkdir(exist_ok=True)
        
        filename = f"{version}_{Path(runtime['url']).name}".lower()
        installer = self.download_file(runtime['url'], self.download_dir / filename)

        if major_version == 10:
            if not self.args.silent:
                print('Cannot extract Visual C++ 2010 runtime. Skipping.')
            return

        try:
            if major_version < 11:
                seven_zip = self.fetch_7zip()
                cab_dir = self.extract_old_installer(seven_zip, installer)
                for cab in cab_dir.glob('*.cab'):
                    self.extract_cab(cab, output_dir)
            else:
                wix_dir = self.fetch_wix()
                bundle_dir = self.extract_burn_bundle(wix_dir, installer)
                for cab in self.find_cabs(bundle_dir):
                    self.extract_cab(cab, output_dir)
                
            self.cleanup_dlls(output_dir)
                
        except Exception as e:
            if not self.args.silent:
                print(f"Error processing {version}: {e}")

    def cleanup_temp(self):
        # Remove temporary files and directories created during processing
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        if self.download_dir.exists():
            shutil.rmtree(self.download_dir)

    def fetch_all(self, include_old_versions: bool = False):
        # Fetch and process all specified runtimes
        if self.args.version:
            for runtime in self.config['runtimes']['x64']:
                if runtime['version'] == self.args.version:
                    self.process_runtime(runtime, include_old_versions)
                    return  # Exit after processing the specified version
            print(f"Version {self.args.version} not found.")
            return
        
        for runtime in self.config['runtimes']['x64']:
            self.process_runtime(runtime, include_old_versions)
        
        if not self.args.no_cleanup:
            self.cleanup_temp()


def main():
    # Main function to parse arguments and initiate the VCRedistManager
    parser = argparse.ArgumentParser(
        description='Fetch Visual C++ redistributables and extract them.')
    parser.add_argument(
        '--include-old-versions',
        '-iov',
        action='store_true',
        help='Include versions older than Visual C++ 2015 (version 14)')
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose output')
    parser.add_argument(
        '--silent',
        '-s',
        action='store_true',
        help='Suppress all output')
    parser.add_argument(
        '--no-cleanup',
        '-nc',
        action='store_true',
        help='Skip cleanup of temporary files and directories')
    parser.add_argument(
        '--version',
        '-ver',
        type=str,
        help='Specify a particular version of the Redistributable to download')
    parser.add_argument(
        '--clean-up',
        '-c',
        action='store_true',
        help='Perform cleanup of temporary files and directories without downloading or installing')
    parser.add_argument(
        '--remove-vcredist',
        '-rv',
        action='store_true',
        help='Remove the vcruntimes folder if it exists')

    args = parser.parse_args()
    
    # Check for conflicting arguments and perform actions accordingly
    if args.clean_up and args.remove_vcredist:
        if not args.silent:
            print("Performing cleanup and removing vcruntimes...")
        manager = VCRedistManager(Path.cwd() / 'vcruntimes', args)
        manager.cleanup_temp()
        
        vcruntimes_path = Path.cwd() / 'vcruntimes'
        if vcruntimes_path.exists() and vcruntimes_path.is_dir():
            shutil.rmtree(vcruntimes_path)
            if not args.silent:
                print("Removed vcruntimes folder.")
        
        if not args.silent:
            print("Cleanup and removal of vcruntimes completed successfully.")
        
        return

    if args.remove_vcredist:
        vcruntimes_path = Path.cwd() / 'vcruntimes'
        if vcruntimes_path.exists() and vcruntimes_path.is_dir():
            shutil.rmtree(vcruntimes_path)
            if not args.silent:
                print("Removed vcruntimes folder.")
        else:
            if not args.silent:
                print("vcruntimes folder did not exist.")
        
        if not args.silent:
            print("Removal of vcruntimes completed successfully.")
        
        return

    if args.clean_up:
        if not args.silent:
            print("Performing cleanup...")
        manager = VCRedistManager(Path.cwd() / 'vcruntimes', args)
        manager.cleanup_temp()
        if not args.silent:
            print("Cleanup completed.")
        return

    manager = VCRedistManager(Path.cwd() / 'vcruntimes', args)
    
    if not args.silent:
        print("Verbose mode enabled.")
    
    if args.version:
        print(f"Specific version requested: {args.version}")
    
    manager.fetch_all(args.include_old_versions)

    if args.no_cleanup:
        print("Cleanup of temporary files will be skipped.")


if __name__ == '__main__':
    main()
