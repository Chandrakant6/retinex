function out_path = enhance_image(image_path, out_path)
% ENHANCE_IMAGE  CLAHE + mild denoise for a fundus image.
%
%   out_path = enhance_image(image_path, out_path)
%
%   Reads image_path, applies CLAHE on the L-channel (illumination-robust
%   contrast enhancement) plus a light bilateral denoise, writes the
%   result to out_path, and returns out_path (so Python gets the same
%   path back it passed in, consistent with the OpenCV fallback).

    I = imread(image_path);

    lab = rgb2lab(I);
    L = lab(:,:,1) / 100;                       % normalize to 0-1
    L_eq = adapthisteq(L, 'ClipLimit', 0.02);    % CLAHE
    lab(:,:,1) = L_eq * 100;
    enhanced = lab2rgb(lab);
    enhanced = im2uint8(enhanced);

    enhanced = imbilatfilt(enhanced);            % mild edge-preserving denoise

    imwrite(enhanced, out_path);
end
