# 📸 Pasta de Imagens dos Produtos

Coloque aqui as fotos dos seus produtos para que o atendente virtual as exiba no chat.

## ✅ Formatos suportados

| Formato | Extensão |
|---|---|
| JPEG | `.jpg`, `.jpeg` |
| PNG  | `.png` |
| WebP | `.webp` |
| GIF  | `.gif` |

## 📐 Especificações recomendadas

| Parâmetro | Recomendado |
|---|---|
| Resolução | 800×1000 px (proporção 4:5) |
| Tamanho máximo | 2 MB por imagem |
| Fundo | Branco ou neutro |
| Qualidade | Alta — são exibidas na vitrine |

## 🔗 Como vincular uma imagem ao produto

No banco de dados (ou no `seed_db.py`), preencha o campo `imagem_local` com o **nome do arquivo**:

```python
{
  "id": "CAL001",
  "nome": "Tênis Runner Pro X",
  ...
  "imagem_local": "tenis-runner-pro-x.jpg",   # ← nome do arquivo aqui
  "imagem_url": "https://...",                 # ← URL de fallback
}
```

O servidor servirá a imagem automaticamente em:
```
http://localhost:8000/products/images/tenis-runner-pro-x.jpg
```

## 📌 Convenção de nomenclatura

Use kebab-case baseado no ID do produto:

| Produto | Nome do arquivo |
|---|---|
| Tênis Runner Pro X (CAL001) | `cal001-tenis-runner.jpg` |
| Camiseta Básica (ROU001) | `rou001-camiseta-basica.jpg` |
| Mochila Urban (ACE001) | `ace001-mochila-urban.jpg` |

## ⚡ Prioridade de exibição

1. `imagem_local` (arquivo nesta pasta) — tem prioridade
2. `imagem_url` (URL externa) — usado como fallback
3. Imagem genérica — se nenhuma das duas estiver disponível

## 🛠️ Script de otimização de imagens (opcional)

Instale o Pillow e rode para otimizar antes de subir em produção:

```bash
pip install Pillow
python -c "
from PIL import Image
import os

for f in os.listdir('.'):
    if f.lower().endswith(('.jpg','jpeg','.png','.webp')):
        img = Image.open(f)
        img.thumbnail((800, 1000))
        img.save(f, optimize=True, quality=85)
        print(f'Otimizado: {f}')
"
```
