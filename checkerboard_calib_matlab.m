function out = checkerboard_calib_matlab(imageDir, squareSize, pattern)
%CHECKERBOARD_CALIB_MATLAB  Camera intrinsics from a plain checkerboard using
% the MATLAB Computer Vision Toolbox (detectCheckerboardPoints /
% estimateCameraParameters). MATLAB-toolbox equivalent of checkerboard_calib.py.
%
% Requires: Computer Vision Toolbox (+ Image Processing Toolbox for imgaussfilt).
%
%   checkerboard_calib_matlab('intrinsics/images2/raw')
%   checkerboard_calib_matlab('intrinsics/images2/raw', 0.079375, '*.png')
%
% Pass the folder of RAW images (intrinsics/imagesX/raw). Outputs go to its
% parent (intrinsics/imagesX):
%   intrinsics_matlab.json     estimated intrinsics (OpenCV-compatible)
%   coverage_matlab.png        corner-coverage map across all views
%   board_positions_matlab.png camera-centric 3D distribution of board poses
%   detections_matlab/         per-image overlays (ok_*.jpg / skip_*.jpg)
%
% Notes on MATLAB vs OpenCV (so the two JSONs are comparable):
%  * MATLAB uses 1-BASED pixel coordinates; OpenCV/COLMAP use 0-based. The
%    principal point is therefore exported as (cx-1, cy-1) so it matches the
%    _opencv output. Focal lengths are unaffected.
%  * MATLAB auto-detects the board size, so there is no CHESS_COLS/ROWS to set.
%  * Error reported is MeanReprojectionError (OpenCV reports RMS) -- close but
%    not identical metrics.

    if nargin < 2 || isempty(squareSize), squareSize = 0.079375; end   % meters
    if nargin < 3 || isempty(pattern),    pattern    = '*.png';   end

    % --- resolve input / output paths -----------------------------------
    imageDir = regexprep(imageDir, '[\\/]+$', '');        % strip trailing sep
    outDir = fileparts(imageDir);                          % parent of /raw
    if isempty(outDir), outDir = '.'; end
    savePath     = fullfile(outDir, 'intrinsics_matlab.json');
    coveragePath = fullfile(outDir, 'coverage_matlab.png');
    boardPosPath = fullfile(outDir, 'board_positions_matlab.png');
    detDir       = fullfile(outDir, 'detections_matlab');
    if ~exist(detDir, 'dir'), mkdir(detDir); end

    % --- gather files ---------------------------------------------------
    listing = dir(fullfile(imageDir, pattern));
    if isempty(listing)
        error('No images matched %s', fullfile(imageDir, pattern));
    end
    files = fullfile({listing.folder}, {listing.name});
    files = sort(files);

    % --- skip unreadable / corrupt files (your data has some) -----------
    readable = true(size(files));
    for i = 1:numel(files)
        try
            imread(files{i});
        catch
            readable(i) = false;
            fprintf('  skip (unreadable): %s\n', files{i});
        end
    end
    files = files(readable);
    if isempty(files)
        error('No readable images in %s', imageDir);
    end

    % --- detect checkerboards -------------------------------------------
    % For a heavily distorted wide lens, add 'HighDistortion', true (R2021b+).
    [imagePoints, boardSize, imagesUsed] = detectCheckerboardPoints(files);
    usedFiles    = files(imagesUsed);
    skippedFiles = files(~imagesUsed);
    nUsed = numel(usedFiles);
    fprintf('Board detected: %dx%d squares  ->  %dx%d inner corners\n', ...
            boardSize(2), boardSize(1), boardSize(2)-1, boardSize(1)-1);
    fprintf('Views used: %d   skipped (no board): %d\n', nUsed, numel(skippedFiles));
    if nUsed < 8
        error('Only %d usable views; aim for ~15-30.', nUsed);
    end

    % image size from the first used image
    I0 = imread(usedFiles{1});
    [h, w, ~] = size(I0);

    % --- calibrate (OpenCV-compatible model: k1,k2,p1,p2,k3) ------------
    worldPoints = generateCheckerboardPoints(boardSize, squareSize);
    params = estimateCameraParameters(imagePoints, worldPoints, ...
        'ImageSize', [h, w], ...
        'EstimateSkew', false, ...
        'NumRadialDistortionCoefficients', 3, ...
        'EstimateTangentialDistortion', true, ...
        'WorldUnits', 'm');

    % --- pull out intrinsics --------------------------------------------
    fx = params.FocalLength(1);   fy = params.FocalLength(2);
    cx = params.PrincipalPoint(1); cy = params.PrincipalPoint(2);
    rd = params.RadialDistortion;  td = params.TangentialDistortion;
    k1 = rd(1); k2 = rd(2);
    if numel(rd) >= 3, k3 = rd(3); else, k3 = 0; end
    p1 = td(1); p2 = td(2);

    % MATLAB 1-based -> OpenCV/COLMAP 0-based principal point
    cx0 = cx - 1;  cy0 = cy - 1;
    K = [fx 0 cx0; 0 fy cy0; 0 0 1];

    fprintf('\n=== Calibration result ===\n');
    fprintf('RMS/mean reproj   : %.4f px   (aim < ~0.5; < 1.0 usable)\n', params.MeanReprojectionError);
    fprintf('resolution (w x h): %d x %d\n', w, h);
    fprintf('fx, fy            : %.3f, %.3f\n', fx, fy);
    fprintf('cx, cy (0-based)  : %.3f, %.3f\n', cx0, cy0);
    fprintf('dist coeffs       : %.6g %.6g %.6g %.6g %.6g\n', k1, k2, p1, p2, k3);

    % --- write JSON (same keys as the _opencv output) -------------------
    out = struct();
    out.image_width  = w;
    out.image_height = h;
    out.camera_matrix = K;
    out.dist_coeffs   = [k1 k2 p1 p2 k3];   % OpenCV order
    out.fx = fx; out.fy = fy; out.cx = cx0; out.cy = cy0;
    out.mean_reproj_error = params.MeanReprojectionError;
    out.model = 'OPENCV (k1,k2,p1,p2,k3)';
    out.note  = 'MATLAB Computer Vision Toolbox; principal point converted to 0-based (OpenCV)';

    try
        txt = jsonencode(out, 'PrettyPrint', true);   % R2021a+
    catch
        txt = jsonencode(out);
    end
    fid = fopen(savePath, 'w');
    fwrite(fid, txt, 'char');
    fclose(fid);
    fprintf('\nSaved -> %s\n', savePath);

    colmap = [fx fy cx0 cy0 k1 k2 p1 p2];
    fprintf('COLMAP OPENCV params: ');
    fprintf('%.6f ', colmap);
    fprintf('\n');

    % --- coverage map ---------------------------------------------------
    save_coverage(imagePoints, [h w], nUsed, coveragePath);
    fprintf('Coverage map written to: %s\n', coveragePath);

    % --- board-pose distribution (camera-centric) -----------------------
    % Companion to the coverage map: coverage shows where corners landed in the
    % IMAGE; this shows where the board was held in SPACE. A good set spans a
    % range of distances and tilts, not a flat wall of boards at one depth.
    try
        save_board_positions(params, nUsed, boardPosPath);
        fprintf('Board positions written to: %s\n', boardPosPath);
    catch ME
        fprintf(2, 'Board-position plot skipped: %s\n', ME.message);
    end

    % --- per-image overlays ---------------------------------------------
    for k = 1:nUsed
        I = imread(usedFiles{k});
        pts = imagePoints(:, :, k);
        pts = pts(all(isfinite(pts), 2), :);
        J = insertMarker(I, pts, 'o', 'Color', 'green', 'Size', 8);
        [~, nm] = fileparts(usedFiles{k});
        imwrite(J, fullfile(detDir, ['ok_' nm '.jpg']));
    end
    for k = 1:numel(skippedFiles)
        I = imread(skippedFiles{k});
        J = insertText(I, [20 20], 'NO BOARD', 'FontSize', 36, ...
                       'BoxColor', 'red', 'TextColor', 'white');
        [~, nm] = fileparts(skippedFiles{k});
        imwrite(J, fullfile(detDir, ['skip_' nm '.jpg']));
    end
    fprintf('Annotated detections written to: %s\n', detDir);
end


function save_coverage(imagePoints, imgSize, nUsed, path)
% Heatmap of all detected corners pooled across views. Dark = no coverage.
    h = imgSize(1); w = imgSize(2);
    radius = max(6, round(w / 160));
    acc = zeros(h, w);
    nPts = 0;
    for k = 1:size(imagePoints, 3)
        pts = imagePoints(:, :, k);
        pts = pts(all(isfinite(pts), 2), :);
        for j = 1:size(pts, 1)
            x = round(pts(j, 1)); y = round(pts(j, 2));
            if x >= 1 && x <= w && y >= 1 && y <= h
                acc(y, x) = acc(y, x) + 1;
                nPts = nPts + 1;
            end
        end
    end
    if max(acc(:)) > 0
        acc = imgaussfilt(acc, radius);
        acc = acc / max(acc(:));
    end
    idx = im2uint8(acc);
    rgb = ind2rgb(idx, jet(256));
    mask = idx == 0;                                  % uncovered -> dark grey
    ch = rgb(:, :, 1); ch(mask) = 30/255; rgb(:, :, 1) = ch;
    ch = rgb(:, :, 2); ch(mask) = 30/255; rgb(:, :, 2) = ch;
    ch = rgb(:, :, 3); ch(mask) = 30/255; rgb(:, :, 3) = ch;
    rgb = insertText(rgb, [12 12], sprintf('%d views, %d corners', nUsed, nPts), ...
                     'FontSize', 22, 'BoxColor', 'black', 'TextColor', 'white');
    imwrite(rgb, path);
end


function save_board_positions(params, nUsed, path)
% Camera-centric 3D distribution of every detected board pose -- the spatial
% companion to the coverage map. Coverage shows where corners landed in the
% IMAGE; this shows where the board was held in SPACE.
%
% This is MATLAB's own showExtrinsics(params,'CameraCentric') figure: the camera
% sits at the origin as a blue frustum looking down +Z, and each detected board
% is drawn as a translucent numbered rectangle at its estimated pose. We let
% showExtrinsics own the (correct) camera-centric viewpoint instead of rolling
% our own 3D view, then only relabel the axes from the calibration's WorldUnits
% (meters) to centimeters -- tick POSITIONS, and hence the geometry, are left
% untouched.

    origFig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 920 660]);
    set(0, 'CurrentFigure', origFig);

    ax = [];
    try
        ax = showExtrinsics(params, 'CameraCentric');   % returns axes (R2017a+)
    catch
        % older signatures return nothing; fall back to the current axes
    end
    if isempty(ax) || ~all(isgraphics(ax))
        ax = gca;
    end
    fig = ancestor(ax, 'figure');                       % follow showExtrinsics

    title(ax, sprintf('Board position distribution (camera-centric) - %d views', nUsed));

    % meters -> centimeters on the labels only (tick positions/data unchanged)
    for c = 'XYZ'
        try
            ticks = get(ax, [c 'Tick']);
            set(ax, [c 'TickMode'], 'manual', [c 'Tick'], ticks, ...
                    [c 'TickLabel'], compose('%g', ticks * 100));
            set(get(ax, [c 'Label']), 'String', sprintf('%c (centimeters)', c));
        catch
            % leave this axis in its native units if anything is unexpected
        end
    end

    try
        exportgraphics(ax, path, 'Resolution', 150);   % R2020a+
    catch
        saveas(fig, path);                             % older releases
    end
    if isgraphics(fig),     close(fig);     end
    if ~isequal(fig, origFig) && isgraphics(origFig), close(origFig); end
end
