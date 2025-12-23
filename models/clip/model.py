
import torch
from transformers import CLIPModel, CLIPProcessor


class ModelImpl:
    """CLIP ViT-Base-Patch32 model implementation.
    
    Smaller, faster model suitable for testing and deployment.
    Supports both CPU and GPU inference.
    """

    def load(self):
        """Load the CLIP model and processor."""
        model_name = "openai/clip-vit-base-patch32"
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model = CLIPModel.from_pretrained(model_name)
        
        # Use GPU if available, otherwise CPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = self.model.to(self.device).eval()
        
        print(f"Model loaded on {self.device}")

    def warmup(self):
        """Warmup the model with dummy inputs."""
        dummy = torch.zeros(1, 3, 224, 224).to(self.device)
        with torch.no_grad():
            self.model.get_image_features(dummy)

    def batch_size(self):
        """Return optimal batch size."""
        return 8 if self.device == "cpu" else 16

    def batch_wait_s(self):
        """Return batch wait time in seconds."""
        return 0.005 if self.device == "cpu" else 0.003

    def encode(self, batch):
        """Encode a batch of images into embeddings.
        
        Args:
            batch: List of dicts with 'image' and optional 'text'
            
        Returns:
            List of normalized embeddings
        """
        images = [b["image"] for b in batch]
        inputs = self.processor(images=images, return_tensors="pt")
        x = inputs["pixel_values"].to(self.device)
        
        with torch.no_grad():
            e = self.model.get_image_features(x)
            e = e / e.norm(dim=-1, keepdim=True)
        
        return e.cpu().tolist()
