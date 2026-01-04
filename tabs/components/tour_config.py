# tour_config.py
from .active_tutorial import TourManager

def setup_tour(main_window):
    tour = TourManager(main_window)
    
    # Step 1: Diagnostics
    tour.add_step(1, lambda: main_window.diag_tab.run_btn, 
                  "Step 1: Diagnostics", 
                  "Always start here to check your drivers.")

    # Step 2: Capture
    tour.add_step(2, lambda: main_window.capture_tab.btn_record, 
                  "Step 2: Recording", 
                  "This tab is currently locked for your safety.\n\n"
                  "It will automatically unlock when you plug in a camera!")

    # Step 3: Converter
    tour.add_step(3, lambda: main_window.converter_tab.btn_select, 
                  "Step 3: Finishing Up", 
                  "Finally, use this tab to convert your footage.")

    return tour