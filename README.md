# Instagram Non-Followers

Script em Python para identificar quem voce segue no Instagram, mas nao segue de volta.

## Requisitos

- Python 3.11+
- Um perfil do navegador ja autenticado no Instagram
- Playwright com Chromium

## Estrutura

- `instagram_nonfollowers.py`: gera `nao_seguidores.json`
- `instagram_filter_famous.py`: remove perfis com mais de 3000 seguidores
- `instagram_unfollow_selected.py`: desfaz o follow dos perfis filtrados
- `instagram_nonfollowers/`: pacote com a logica do projeto
- `requirements.txt`: dependencia Python do projeto

## Instalacao

### Windows

1. Crie e ative o ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

2. Instale as dependencias:

```powershell
pip install -r requirements.txt
```

3. Instale o Chromium do Playwright:

```powershell
python -m playwright install chromium
```

### Ubuntu

1. Crie e ative o ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Instale o Chromium do Playwright:

```bash
python -m playwright install chromium
```

### macOS

1. Crie e ative o ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instale as dependencias:

```bash
pip install -r requirements.txt
```

3. Instale o Chromium do Playwright:

```bash
python -m playwright install chromium
```

## Como passar o `user-data-dir`

Esse parametro deve apontar para a **pasta do perfil do navegador**, nao para o executavel do Chrome.

### Windows

Use a pasta raiz do perfil:

```text
C:\Users\SEU_USUARIO\AppData\Local\Google\Chrome\User Data
```

Exemplo real:

```text
C:\Users\fsodi\AppData\Local\Google\Chrome\User Data
```

### Ubuntu

Use a pasta do perfil do Chrome/Chromium:

```text
/home/SEU_USUARIO/.config/google-chrome/
```

Exemplo real:

```text
/home/fsodi/.config/google-chrome/
```

### macOS

Use a pasta do perfil do Chrome:

```text
/Users/SEU_USUARIO/Library/Application Support/Google/Chrome/
```

Exemplo real:

```text
/Users/fsodi/Library/Application Support/Google/Chrome/
```

Se o navegador estiver aberto usando esse perfil, feche todas as janelas antes de rodar.

## Como usar

### 1. Gerar `nao_seguidores.json`

**Windows**

```powershell
.\.venv\Scripts\python.exe .\instagram_nonfollowers.py --username facova.jpg --user-data-dir "C:\Users\fsodi\AppData\Local\Google\Chrome\User Data"
```

**Ubuntu**

```bash
python instagram_nonfollowers.py --username facova.jpg --user-data-dir "/home/fsodi/.config/google-chrome/"
```

**macOS**

```bash
python instagram_nonfollowers.py --username facova.jpg --user-data-dir "/Users/fsodi/Library/Application Support/Google/Chrome/"
```

### 2. Filtrar perfis com mais de 3000 seguidores

**Windows**

```powershell
.\.venv\Scripts\python.exe .\instagram_filter_famous.py --input .\nao_seguidores.json --output .\nao_seguidores_filtrados.json --user-data-dir "C:\Users\fsodi\AppData\Local\Google\Chrome\User Data"
```

**Ubuntu**

```bash
python instagram_filter_famous.py --input nao_seguidores.json --output nao_seguidores_filtrados.json --user-data-dir "/home/fsodi/.config/google-chrome/"
```

**macOS**

```bash
python instagram_filter_famous.py --input nao_seguidores.json --output nao_seguidores_filtrados.json --user-data-dir "/Users/fsodi/Library/Application Support/Google/Chrome/"
```

### 2.1 Alterar o limite do filtro

Se quiser usar outro limite, passe `--threshold`.

```powershell
.\.venv\Scripts\python.exe .\instagram_filter_famous.py --input .\nao_seguidores.json --output .\nao_seguidores_filtrados.json --user-data-dir "C:\Users\fsodi\AppData\Local\Google\Chrome\User Data" --threshold 5000
```

```bash
python instagram_filter_famous.py --input nao_seguidores.json --output nao_seguidores_filtrados.json --user-data-dir "/home/fsodi/.config/google-chrome/" --threshold 10000
```

### 3. Remover o follow dos perfis filtrados

**Windows**

```powershell
.\.venv\Scripts\python.exe .\instagram_unfollow_selected.py --input .\nao_seguidores_filtrados.json --output .\nunfollow_report.json --user-data-dir "C:\Users\fsodi\AppData\Local\Google\Chrome\User Data"
```

**Ubuntu**

```bash
python instagram_unfollow_selected.py --input nao_seguidores_filtrados.json --output unfollow_report.json --user-data-dir "/home/fsodi/.config/google-chrome/"
```

**macOS**

```bash
python instagram_unfollow_selected.py --input nao_seguidores_filtrados.json --output unfollow_report.json --user-data-dir "/Users/fsodi/Library/Application Support/Google/Chrome/"
```

## Exemplos com opcoes

### Rodar sem interface grafica

```powershell
.\.venv\Scripts\python.exe .\instagram_nonfollowers.py --username facova.jpg --user-data-dir "C:\Users\fsodi\AppData\Local\Google\Chrome\User Data" --headless
```

### Aumentar o intervalo entre rolagens

```bash
python instagram_nonfollowers.py --username facova.jpg --user-data-dir "/home/fsodi/.config/google-chrome/" --min-delay 2 --max-delay 5
```

### Filtrar com passos mais lentos

```bash
python instagram_filter_famous.py --input nao_seguidores.json --output nao_seguidores_filtrados.json --user-data-dir "/Users/fsodi/Library/Application Support/Google/Chrome/" --min-delay 2 --max-delay 4
```

### Filtrar com outro limite de seguidores

```bash
python instagram_filter_famous.py --input nao_seguidores.json --output nao_seguidores_filtrados.json --user-data-dir "/Users/fsodi/Library/Application Support/Google/Chrome/" --threshold 8000
```

### Rodar o unfollow com mais pausa

```bash
python instagram_unfollow_selected.py --input nao_seguidores_filtrados.json --output unfollow_report.json --user-data-dir "/Users/fsodi/Library/Application Support/Google/Chrome/" --min-delay 3 --max-delay 6
```

## Saida

O JSON gerado segue este formato:

```json
{
  "total_seguindo": 1400,
  "total_seguidores": 500,
  "total_nao_seguidores": 0,
  "nao_seguidores": [
    {
      "insta": "@username",
      "link": "https://www.instagram.com/username"
    }
  ],
  "validacao": {
    "esperado_seguidores": 500,
    "encontrado_seguidores": 490,
    "esperado_seguindo": 1400,
    "encontrado_seguindo": 1400,
    "bate_seguidores": false,
    "bate_seguindo": true
  }
}
```

Se a quantidade lida nao bater com a exibida no perfil, o campo `validacao` mostra a comparacao entre o valor esperado e a quantidade unica realmente capturada.
