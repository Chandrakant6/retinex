"""
=====================================================================
 ML INTEGRATION POINT — this is the ONLY file the AI/ML engineer
 needs to touch. Replace predict() with real PyTorch inference.
 Keep the input/output contract exact and nothing else in the app
 (backend routes, frontend) needs to change.
=====================================================================

CONTRACT
--------
predict(image_path: str) -> dict

Input:
    image_path — path to the *enhanced* fundus image on disk (str)

Output dict (all keys required):
    {
        "icdr_level":    int,            # 0-4, International Clinical DR scale
        "icdr_label":    str,             # human-readable label
        "referable":     bool,            # True if icdr_level >= 2
        "confidence":    float,           # 0-1, ideally calibrated
        "probabilities": [float] * 5,     # softmax over 5 classes, sums to ~1
        "gradcam_path":  str | None,      # absolute path to a saved heatmap
                                           # overlay PNG, or None if unavailable
    }

REAL IMPLEMENTATION SKETCH (delete the mock below and use this shape)
-----------------------------------------------------------------------
    import torch
    from torchvision import transforms
    from PIL import Image
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.image import show_cam_on_image

    _model = torch.load("checkpoints/model.pt", map_location="cpu").eval()
    _transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    def predict(image_path: str) -> dict:
        img = Image.open(image_path).convert("RGB")
        x = _transform(img).unsqueeze(0)

        with torch.no_grad():
            logits = _model(x)
            probs = torch.softmax(logits, dim=1)[0].tolist()
        level = int(torch.argmax(logits, dim=1).item())

        cam = GradCAM(model=_model, target_layers=[_model.layer4[-1]])
        grayscale_cam = cam(input_tensor=x)[0]
        overlay = show_cam_on_image(np.array(img.resize((224,224)))/255.0, grayscale_cam)
        cam_path = image_path.replace("enhanced.png", "gradcam.png")
        Image.fromarray(overlay).save(cam_path)

        return {
            "icdr_level": level,
            "icdr_label": ICDR_LABELS[level],
            "referable": level >= 2,
            "confidence": round(max(probs), 3),
            "probabilities": [round(p, 3) for p in probs],
            "gradcam_path": cam_path,
        }
=====================================================================
"""
import random

ICDR_LABELS = {
    0: "No DR",
    1: "Mild NPDR",
    2: "Moderate NPDR",
    3: "Severe NPDR",
    4: "Proliferative DR",
}


def predict(image_path: str) -> dict:
    """
    MOCK — deterministic per image (seeded on filename) so the same image
    always returns the same result during demo/dev. Replace this entire
    function body with real inference; keep the signature and return shape.
    """
    random.seed(hash(image_path) % (2**32))
    level = random.choices([0, 1, 2, 3, 4], weights=[35, 25, 25, 10, 5])[0]

    probs = [0.02] * 5
    probs[level] = 0.70 + random.random() * 0.2
    remaining = 1 - probs[level]
    others = [i for i in range(5) if i != level]
    for i in others:
        probs[i] = remaining / len(others)
    total = sum(probs)
    probs = [round(p / total, 3) for p in probs]

    return {
        "icdr_level": level,
        "icdr_label": ICDR_LABELS[level],
        "referable": level >= 2,
        "confidence": max(probs),
        "probabilities": probs,
        "gradcam_path": None,  # real implementation saves a PNG and returns its path
    }
