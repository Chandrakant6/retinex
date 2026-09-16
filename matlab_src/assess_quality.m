function r = assess_quality(image_path)
% ASSESS_QUALITY  Evaluate a fundus image for gradability.
%
%   r = assess_quality(image_path)
%
%   Returns a struct with fields matching the Python contract exactly
%   (see backend/processing.py -> _matlab_struct_to_dict):
%       r.gradable  (logical)
%       r.score     (double, 0-1)
%       r.reasons   (cell array of strings)
%       r.guidance  (string, '' if gradable)
%       r.engine    ('matlab')

    I = imread(image_path);
    if size(I, 3) == 3
        G = double(rgb2gray(I));
    else
        G = double(I);
    end

    % --- Focus: variance of Laplacian (higher = sharper) ---
    lap = fspecial('laplacian');
    focus = var(reshape(imfilter(G, lap), [], 1));

    % --- Illumination: mean brightness over the retinal (non-black) region ---
    mask = G > 10;
    if any(mask(:))
        illum = mean(G(mask));
    else
        illum = 0;
    end

    % --- Field of view: fraction of frame occupied by the retinal circle ---
    fov = sum(mask(:)) / numel(mask);

    focus_score = min(focus / 150.0, 1.0);
    illum_score = max(0, 1 - abs(illum - 120) / 120.0);
    fov_score   = min(fov / 0.35, 1.0);

    score = 0.5*focus_score + 0.3*illum_score + 0.2*fov_score;

    reasons = {};
    if focus_score < 0.4
        reasons{end+1} = 'out_of_focus';
    end
    if illum_score < 0.4
        reasons{end+1} = 'poor_illumination';
    end
    if fov_score < 0.4
        reasons{end+1} = 'insufficient_field_of_view';
    end

    gradable = (score > 0.45) && isempty(reasons);

    r.gradable = gradable;
    r.score = round(score, 3);
    r.reasons = reasons;
    if gradable
        r.guidance = '';
    else
        r.guidance = ['Please recapture: ', strjoin(strrep(reasons, '_', ' '), ', '), '.'];
    end
    r.engine = 'matlab';
end
