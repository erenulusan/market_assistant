from pathlib import Path
import numpy as np
import faiss
from rich import print

ROOT= Path(__file__).resolve().parents[1]
DATA_DIR= ROOT / "data"

EMB_PATH = DATA_DIR / "product_embeddings.npy"
ID_PATH= DATA_DIR / "product_ids.npy"
INDEX_PATH= DATA_DIR / "product_index.faiss"


def main():
    #embedding idleri al
    embeddings= np.load(EMB_PATH)
    ids= np.load(ID_PATH)
    #print(f" [Embedding Shape]: {embeddings.shape}")
    #print(f" [IDs shape]: {ids.shape}")

    # faiss için float 32 dönüşümü (ilk scriptte float32 ye çevirmiştim ama ufak bi check ekleyelim)
    if embeddings.dtype != np.float32:
        embeddings= embeddings.astype("float32")

    n, dim = embeddings.shape

    #idx olustur (cosine similarity icin normalize_embeddings= True kullandik  o yüzden IP)
    index= faiss.IndexFlatIP(dim) #inner product
    index.add(embeddings)
    print("index vektör sayisi", index.ntotal)

    #kaydet
    faiss.write_index(index, str(INDEX_PATH))
    print("faiss index kaydedildi")


if __name__ == "__main__":
    main()