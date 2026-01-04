# core/capture_manager.py
import os
import shutil
import glob
import datetime
import subprocess

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
                return True, 999 
            
            total, used, free = shutil.disk_usage(path)
            free_gb = free // (2**30)
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
            return False 
        return os.access(devices[0], os.R_OK | os.W_OK)

    def get_meteorological_season(self):
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
        
        # CHANGED: Unified naming logic. 
        # All captures now produce a _MASTER.dv file so autosplit works consistently.
        if fmt == "mini_dv":
            final_folder = f"tape_{tape}_dv-{yymm}_{yymm}"
            filename_base = f"{lname.lower()}_{fname.lower()}_mdv_t{tape}_MASTER.dv"
        else:
            # For Digital8, we still respect the manual label for the FOLDER name,
            # but the FILE name uses the standard _MASTER format.
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
        executable = shutil.which("dvcont")
        if not executable:
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
        return f"dvgrab --format raw - | tee {output_path} | mpv --wid={window_id} --profile=low-latency -"

    def get_preview_command(self, window_id):
        return f"dvgrab -format raw - | mpv --wid={window_id} --profile=low-latency -"

    def get_autosplit_command(self, master_file):
        folder_path = os.path.dirname(master_file)
        # This replace is crucial and now works for ALL formats
        base_name = os.path.basename(master_file).replace("_MASTER.dv", "-")
        return f'cd "{folder_path}" && dvgrab --autosplit --timestamp --size 0 --format raw -I "{master_file}" "{base_name}"'

    def find_split_files(self, master_file):
        folder_path = os.path.dirname(master_file)
        base_name = os.path.basename(master_file).replace("_MASTER.dv", "-")
        files = glob.glob(os.path.join(folder_path, f"{base_name}*.dv"))
        return [f for f in files if "_MASTER.dv" not in f]

    def has_valid_timestamp(self, file_path):
        try:
            filename = os.path.basename(file_path)
            if "19" in filename or "20" in filename:
                 return True
        except:
            pass
        return False

    def batch_rename_files(self, file_list, date_str):
        for f in file_list:
            path, name = os.path.split(f)
            new_name = name.replace(".dv", f"_{date_str}.dv")
            new_full_path = os.path.join(path, new_name)
            try:
                os.rename(f, new_full_path)
            except OSError as e:
                print(f"Rename error: {e}")
