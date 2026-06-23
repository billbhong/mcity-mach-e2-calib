% Run checkerboard intrinsics calibration for all 6 cameras (MATLAB toolbox).
% MATLAB equivalent of run_checkerboard_calib.ps1.
% Run from the repo root in MATLAB:  run_checkerboard_calib_matlab

for i = 1:6
    raw = fullfile('intrinsics', sprintf('images%d', i), 'raw');
    if ~isfolder(raw)
        fprintf('Skipping camera %d  (no folder: %s)\n', i, raw);
        continue;
    end
    fprintf('=== Calibrating camera %d  (%s) ===\n', i, raw);
    try
        checkerboard_calib_matlab(raw);
    catch ME
        fprintf(2, 'Camera %d failed: %s\n', i, ME.message);
    end
    fprintf('Completed calibration for camera %d\n', i);
end
