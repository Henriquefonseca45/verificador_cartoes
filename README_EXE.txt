COMO GERAR O .EXE DO VERIFICADOR DE CARTOES RVB

1) Coloque estes arquivos na pasta do projeto:
   - build_exe.bat
   - verificador_cartoes.spec

2) Confirme que a pasta do projeto contem:
   - desktop_app.py
   - main.py
   - config.py
   - rules.py
   - reader_pdf.py
   - extractor.py
   - classifier.py
   - grouper.py
   - exporter.py
   - clients_colors.json
   - logo_rvb.png
   - logo_rvb.ico  (icone opcional, mas recomendado)

3) Instale o PyInstaller no Windows:
   pip install pyinstaller

4) Para gerar pelo .bat:
   - clique duas vezes em build_exe.bat

5) Ou gere pelo .spec:
   pyinstaller --noconfirm verificador_cartoes.spec

6) Resultado esperado:
   - pasta dist\VerificadorCartoesRVB
   - dentro dela fica o executavel

OBSERVACOES:
- Se nao tiver logo_rvb.ico, remova a linha --icon "logo_rvb.ico" do .bat
  e remova icon='logo_rvb.ico' do .spec
- O .exe precisa ficar junto da pasta criada pelo PyInstaller quando usar
  o modo padrao de pasta (onedir), que e o mais seguro para esse projeto.
- Depois de gerar, teste:
  - abrir o app
  - selecionar PDFs
  - processar
  - abrir output e logs
