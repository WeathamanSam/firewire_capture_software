# core/capture_manager.py
import os
import shutil
import glob
import datetime
import subprocess
import re

class CaptureManager:
    def __init__(self, config):
        self.config = config

    def check_disk_space(self):
        """
        Checks if there is enough free space on the drive.
        Returns: (is_safe: bool, free_gb: int)
        """
        path = self.config.get("root_archive_path")
        try:
            if not os.path.exists(path):
                # If the folder doesn't exist yet, we assume the drive is mounted and has space
                # or that the path will be created on the root drive.
                return True, 999 
            
            total, used, free = shutil.disk_usage(path)
            free_gb = free // (2**30)
            
            # DV is ~13GB per hour. We warn if less than 15GB free.
            return free_gb >= 15, free_gb
        except Exception:
            return True, 0

    def check_firewire_permissions(self):
        """
        Checks if the current user has write access to the FireWire device.
        Returns: True if writable, False if we need sudo.
        """
        devices = glob.glob('/dev/fw*')
        if not devices:
            return False # No devices found, so we technically don't have access
        
        # Check the first device found (usually fw0)
        return os.access(devices[0], os.R_OK | os.W_OK)

    def get_meteorological_season(self):
        """Calculates the seasonal folder name (e.g. '2312_2402')"""
        today = datetime.date.today()
        month = today.month
        year = today.year
        
        if month in [12, 1, 2]:
            start_month = 12
            start_year = year - 1 if month in [1, 2] else year
        elif month in [3, 4, 5]:
            start_month = 3
            start_year = year
        elif month in [6, 7, 8]:
            start_month = 6
            start_year = year
        else: 
            start_month = 9
            start_year = year

        end_month = (start_month + 2)
        end_year = start_year
        if end_month > 12:
            end_month -= 12
            end_year += 1
            
        start_str = f"{str(start_year)[2:]}{start_month:02d}"
        end_str = f"{str(end_year)[2:]}{end_month:02d}"
        return f"{start_str}_{end_str}"

    def generate_paths(self, session_data):
        """
        Generates the full folder structure and filename based on session data.
        Returns: (directory_path, full_file_path, filename_only)
        """
        root_path = self.config.get("root_archive_path")
        fname, lname, tape, fmt, manual_lbl = session_data
        
        season_folder = self.get_meteorological_season()
        client_folder = f"{lname.lower()}_{fname.lower()}"
        format_folder = fmt

        now = datetime.datetime.now()
        yymm = now.strftime("%y%m")
        timestamp_str = now.strftime("%Y.%m.%d_%H-%M-%S")

        # CHANGED: Unified naming logic. 
        # All captures now produce a _MASTER.dv file so autosplit works consistently.
        if fmt == "mini_dv":
            final_folder = f"tape_{tape}_dv-{yymm}_{yymm}"
            filename_base = f"{lname.lower()}_{fname.lower()}_mdv_t{tape}_MASTER.dv"
        else:
            # For Digital8, we still respect the manual label for the FOLDER name,
            # but the FILE name uses the standard _MASTER format to ensure autosplit works.
            clean_label = manual_lbl.replace(" ", "_").lower()
            final_folder = clean_label if clean_label else f"tape_{tape}_d8-{yymm}"
            filename_base = f"{lname.lower()}_{fname.lower()}_d8_t{tape}_MASTER.dv"

        full_dir_path = os.path.join(
            root_path,
            format_folder,
            season_folder,
            client_folder,
            "dv_format",
            final_folder
        )
        
        full_path = os.path.join(full_dir_path, filename_base)
        
        return full_dir_path, full_path, filename_base

    def run_tape_control(self, action):
        """Runs dvcont commands like play, stop, rewind."""
        # Dynamic lookup instead of hardcoded path
        executable = shutil.which("dvcont")
        if not executable:
            # Fallback for systems where it might be in /usr/local/bin not in path
            executable = "/usr/bin/dvcont"
            
        if not os.path.exists(executable) and shutil.which("dvcont") is None:
             print(f"Error: Could not find dvcont for {action}")
             return

        cmd = [executable, action]
        try:
            subprocess.Popen(cmd)
        except FileNotFoundError:
            print(f"Error: Could not execute {cmd}")

    def get_capture_command(self, output_path, window_id):
        """Returns the shell command string for recording."""
        return f"dvgrab --format raw - | tee {output_path} | mpv --wid={window_id} --profile=low-latency -"

    def get_preview_command(self, window_id):
        """Returns the shell command string for preview only."""
        return f"dvgrab -format raw - | mpv --wid={window_id} --profile=low-latency -"

    def get_autosplit_command(self, master_file):
        """Generates the dvgrab autosplit command string."""
        folder_path = os.path.dirname(master_file)
        # This replace is crucial and now works for ALL formats
        base_name = os.path.basename(master_file).replace("_MASTER.dv", "-")
        
        # We cd into the directory first to ensure dvgrab writes files locally
        return f'cd "{folder_path}" && dvgrab --autosplit --timestamp --size 0 --format raw -I "{master_file}" "{base_name}"'

    def find_split_files(self, master_file):
        """Finds files generated by autosplit in the master file's directory."""
        folder_path = os.path.dirname(master_file)
        base_name = os.path.basename(master_file).replace("_MASTER.dv", "-")
        
        # Look for files starting with base_name
        files = glob.glob(os.path.join(folder_path, f"{base_name}*.dv"))
        
        # Ensure we exclude the original MASTER file if it was caught by the glob
        return [f for f in files if "_MASTER.dv" not in f]

    def has_valid_timestamp(self, file_path):
        """Checks if a file has a digital date stamp (YYYY.MM.DD) in its name."""
        try:
            filename = os.path.basename(file_path)
            # dvgrab puts dates like 2004.05.21 in the filename if found
            if "19" in filename or "20" in filename:
                 return True
        except:
            pass
        return False

    def batch_rename_files(self, file_list, date_str):
        """
        Renames files to inject a manual date in the format the Converter expects.
        Converts the sequence number (e.g. 001) to a fake time (00-00-01)
        so the filename matches: Base-YYYY.MM.DD_HH-MM-SS.dv
        """
        for f in file_list:
            path, name = os.path.split(f)
            
            # Match files ending in -NUM.dv (e.g. tape-001.dv)
            match = re.search(r"-(\d+)\.dv$", name)
            
            if match:
                seq_num = match.group(1)
                # Convert sequence '001' to time '00-00-01'
                fake_time = f"00-00-{int(seq_num):02d}"
                
                # Strip the -001.dv part to get the base
                base_name = name[:match.start()]
                
                # Construct new name: firstname_lastname_t01-1990.01.01_00-00-01.dv
                new_name = f"{base_name}-{date_str}_{fake_time}.dv"
            else:
                # Fallback if pattern doesn't match, just append date (better than crashing)
                new_name = name.replace(".dv", f"_{date_str}.dv")

            new_full_path = os.path.join(path, new_name)
            try:
                os.rename(f, new_full_path)
            except OSError as e:
                print(f"Rename error: {e}")
