# MKV Renamer

**Versão 1.0.0 — By Tokon**

Aplicativo para Windows com interface gráfica escura para renomear arquivos de vídeo no estilo Scene/P2P.

## Recursos

- Renomeação automática de filmes e episódios com pré-visualização.
- Fontes de vídeo predefinidas e personalizadas (cadastro e remoção).
- Opções de copiar e renomear em pasta de saída ou renomear os arquivos originais.
- Renomeação em lote por lista TXT.
- Detecção de informações de vídeo e áudio por ferramentas externas compatíveis.
- Indicador de progresso e tela **Sobre** em tema escuro.

## Requisitos

- Windows e Python 3 instalado com suporte a Tkinter.
- Para identificação automática de mídias, recomenda-se **MKVToolNix** (`mkvmerge`) no PATH ou instalado em `C:\Program Files\MKVToolNix`. O programa também pode utilizar `ffprobe` ou MediaInfo CLI, quando disponíveis.
- Para arrastar e soltar arquivos (opcional): `pip install tkinterdnd2`.

## Executar

1. Baixe os arquivos do repositório (menu **Code → Download ZIP**) e extraia-os.
2. Execute `INICIAR.bat` ou, no terminal, `py -3 Scene_Renamer.py`.

## Gerar um executável

Execute `CRIAR_EXE.bat` no Windows. O script instala o PyInstaller e gera o executável na pasta `dist`. É necessário Python 3 e acesso à instalação de pacotes.

> **Nota:** O executável deve ser compilado no Windows. O arquivo ZIP deste repositório contém o código-fonte, não um `.exe` já compilado.

## Uso

Selecione um arquivo ou uma pasta, escolha a fonte de vídeo e as demais opções, confira a prévia e inicie a operação. Para preservar os arquivos originais, escolha o modo de cópia para a pasta de saída.

## Publicar no GitHub

1. Crie um repositório novo no GitHub chamado `MKV-Renamer`.
2. Envie os arquivos **da raiz** deste projeto (README, código, scripts e `.github`).
3. Crie uma release com a tag `v1.0.0` se desejar disponibilizar uma versão identificada.

## Licença

Nenhuma licença de distribuição foi definida neste pacote. Adicione um arquivo `LICENSE` com a licença escolhida antes de autorizar formalmente a reutilização do código por terceiros.

## Licença

Distribuído sob a [Licença MIT](LICENSE). © 2026 Tokon.
