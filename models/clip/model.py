
import torch
from transformers import CLIPModel, CLIPProcessor

class ModelImpl:
    def load(self):
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14")
        self.model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14").cuda().eval()

    def warmup(self):
        dummy = torch.zeros(1,3,224,224).cuda()
        with torch.no_grad():
            self.model.get_image_features(dummy)

    def batch_size(self): return 16
    def batch_wait_s(self): return 0.003

    def encode(self, batch):
        images = [b["image"] for b in batch]
        inputs = self.processor(images=images, return_tensors="pt")
        x = inputs["pixel_values"].cuda()
        with torch.no_grad():
            e = self.model.get_image_features(x)
            e = e / e.norm(dim=-1, keepdim=True)
        return e.cpu().tolist()
