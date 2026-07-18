#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whisper Offline Subtitler - PySide6 GUI
Rewritten from Tkinter to match the modern AutoCaption look & feel, 
while preserving the local Whisper.cpp and FFmpeg subprocess execution logic.

Copyright (c) 2026 Zenny126. Licensed under the MIT License.
"""

import sys
from PySide6 import QtWidgets
from src.core.utils import check_system_assets
from src.ui.downloader import DownloaderDialog
from src.ui.main_window import MainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    
    missing = check_system_assets()
    if missing:
        # Launch downloader dialog first
        downloader = DownloaderDialog(missing)
        if downloader.exec() == QtWidgets.QDialog.Accepted:
            window = MainWindow()
            window.show()
            sys.exit(app.exec())
        else:
            sys.exit(0)
    else:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--demucs-worker":
        try:
            import torch
            import torchaudio
            import soundfile as sf
            
            def custom_load(uri, *args, **kwargs):
                data, samplerate = sf.read(uri, dtype='float32')
                tensor = torch.from_numpy(data)
                if len(tensor.shape) == 1:
                    tensor = tensor.unsqueeze(0)
                else:
                    tensor = tensor.t()
                return tensor, samplerate

            def custom_save(uri, src, sample_rate, *args, **kwargs):
                data = src.t().cpu().numpy()
                sf.write(uri, data, sample_rate)
            
            torchaudio.load = custom_load
            torchaudio.save = custom_save
            
            from demucs.separate import main as demucs_main
            
            # Reconstruct sys.argv for demucs
            # demucs args: ["demucs", "-n", model_name, "--two-stems", "vocals", "-o", out_dir, input_file]
            demucs_args = ["demucs", "-n", sys.argv[2], "--two-stems", "vocals", "-o", sys.argv[3]]
            
            # Add device configuration
            if len(sys.argv) > 5:
                demucs_args.extend(["-d", sys.argv[5]])
                
            # Add segment optimization (saves VRAM on GPU)
            if len(sys.argv) > 6 and sys.argv[6] != "None":
                demucs_args.extend(["--segment", sys.argv[6]])
                
            # Add shifts for higher quality
            if len(sys.argv) > 7 and sys.argv[7] != "1":
                demucs_args.extend(["--shifts", sys.argv[7]])
                
            # Add input track
            demucs_args.append(sys.argv[4])
            
            sys.argv = demucs_args
            demucs_main()
            sys.exit(0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            sys.exit(1)
            
    main()
