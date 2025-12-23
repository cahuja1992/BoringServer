
import torch, torch.nn as nn
from transformers import FlavaModel, FlavaProcessor

class ModelImpl:
    def load(self):
        self.num_classes = 10
        self.processor = FlavaProcessor.from_pretrained("facebook/flava-full")
        base = FlavaModel.from_pretrained("facebook/flava-full")
        self.classifier = nn.Linear(base.config.hidden_size, self.num_classes)
        self.model = base.cuda().eval()
        self.classifier = self.classifier.cuda().eval()

    def warmup(self):
        dummy_img = torch.zeros(1,3,224,224).cuda()
        dummy_txt = ["warmup"]
        inp = self.processor(images=dummy_img, text=dummy_txt, return_tensors="pt")
        inp = {k:v.cuda() for k,v in inp.items()}
        with torch.no_grad():
            out = self.model(**inp)
            self.classifier(out.multimodal_embeddings)

    def batch_size(self): return 8
    def batch_wait_s(self): return 0.005

    def encode(self, batch):
        images = [b["image"] for b in batch]
        texts = [b.get("text","") for b in batch]
        inp = self.processor(images=images, text=texts, return_tensors="pt", padding=True)
        inp = {k:v.cuda() for k,v in inp.items()}
        with torch.no_grad():
            out = self.model(**inp)
            logits = self.classifier(out.multimodal_embeddings)
        return logits.cpu().tolist()
