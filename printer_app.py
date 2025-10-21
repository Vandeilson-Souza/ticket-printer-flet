from datetime import datetime
import qrcode
from waitress import serve
from flask import Flask, request
from PIL import Image, ImageDraw, ImageFont
import os
import subprocess

class ImageGenerator:
    def __init__(self, IMAGE_SIZE):
        self.image = None
        self.image_path = None
        self.IMAGE_SIZE = IMAGE_SIZE
        self.FONT_SIZE = 20
        self.CODE_FONT_SIZE = 32

    def create_image(self, created_date, code, services, header, footer):
        self.image = Image.new("RGB", self.IMAGE_SIZE, color=(255, 255, 255))
        draw = ImageDraw.Draw(self.image)
        font = ImageFont.truetype("arial.ttf", size=self.FONT_SIZE)
        code_font = ImageFont.truetype("arial.ttf", size=self.CODE_FONT_SIZE)

        # Define os blocos de texto
        header_block = header
        code_block = f"Código: {code}"
        services_block = f"Serviços: {services}"
        date_block = f"Data: {created_date}"
        print('data',date_block)
        footer_block = footer

        # Define a posição y centralizada para cada bloco de texto
        y_positions = [
            10,
            self.CODE_FONT_SIZE + 30,
            self.FONT_SIZE * 2 + 90,
            self.FONT_SIZE * 3 + 120,
            self.FONT_SIZE * 3 + 170,
        ]

        print('y_positions',y_positions)

        # Escreve cada bloco de texto na imagem
        for block, y in zip([header_block, code_block, services_block, date_block, footer_block], y_positions):
            bbox = draw.textbbox((0, 0), block, font=code_font if "Código:" in block else font)
            w = bbox[2] - bbox[0]
            x = (self.IMAGE_SIZE[0] - w) // 2
            draw.text((x, y), block, font=code_font if "Código:" in block else font, fill=(0, 0, 0))

        date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.image_path = os.path.join(os.getcwd(), "ticket", f"{date}.png")

        self.image.save(self.image_path)
        return self.image_path

    def create_qrcode(self, code):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=4)
        qr.add_data(code)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.qr_path = os.path.join(os.getcwd(), "ticket", f"{date}QR.png")
        img.save(self.qr_path)
        return self.qr_path


    def combine(self):
        img = Image.open(self.image_path)
        img2 = Image.open(self.qr_path)
        img2 = img2.resize((100, 100))
        img_width, img_height = img.size
        spacer = Image.new('RGB', (img_width, 5), color='white')  # Adicionando um espaço de 50 pixels entre as imagens
        img_with_spacer = Image.new('RGB', (img_width, img_height + 100),color='white')  # Aumentando o height em 100 pixels
        img_with_spacer.paste(spacer, (0, img_height))  # Colando o espaço primeiro
        img_with_spacer.paste(img, (0, 0))  # Colando a imagem original
        img_with_spacer.paste(img2, (100, img_height - 50))  # Colando a imagem QR abaixo do espaço
        img_with_spacer.save(self.image_path)
        return self.image_path


app = Flask(__name__)

@app.route("/imprimir")
def printer_connect():
    try:
        image_generator = ImageGenerator(IMAGE_SIZE=(300, 300))
        created_date = request.args.get('created_date')
        code = request.args.get('code')
        services = request.args.get('services')
        header = request.args.get('header')
        footer = request.args.get('footer')
        
        print(f"Parâmetros recebidos: created_date={created_date}, code={code}, services={services}, header={header}, footer={footer}")
        
        data = image_generator.create_image(created_date=created_date, code=code, services=services, header=header, footer=footer)
        print(f"Imagem criada: {data}")

        imagem = data
        impressora = 'ticket-printer'
        largura_pagina = '1000'
        altura_pagina = '1200'
        fator_zoom = '200'

        command = ['mspaint', '/pt', imagem, impressora, '1', largura_pagina, altura_pagina, '/z', fator_zoom]
        print(f"Executando comando: {command}")
        subprocess.check_call(command)
        print("Comando executado com sucesso")
    except Exception as e:
        print(f"Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro ao imprimir: {str(e)}"
    return "Imprimindo"



@app.route("/imprimir/qrcode")
def printer_connect_qrcode():
    try:
        image_generator = ImageGenerator(IMAGE_SIZE=(300, 300))
        created_date = request.args.get('created_date')
        code = request.args.get('code')
        services = request.args.get('services')
        header = request.args.get('header')
        footer = request.args.get('footer')
        qrcode = request.args.get('qrcode')
        image_generator.create_image(created_date=created_date, code=code, services=services, header=header, footer=footer)
        image_generator.create_qrcode(qrcode)
        image = image_generator.combine()

        # envia a imagem para a impressora
        impressora = 'ticket-printer'
        largura_pagina = '1000'
        altura_pagina = '1200'
        fator_zoom = '200'

        subprocess.run(['mspaint', '/pt', image, impressora, '1', largura_pagina, altura_pagina, '/z', fator_zoom],
                       shell=True)
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Erro ao executar o comando: {e}")
        return "Erro ao imprimir"
    return "Imprimindo"


if __name__ == '__main__':
    if not os.path.exists("ticket"):
        os.makedirs("ticket")
    
    print("\n=============================================")
    print("Aplicativo de Impressao em Funcionamento")
    print("Mantenha esta janela aberta para o aplicativo funcionar.")
    print("Teste a impressao acessando pelo navegador: http://localhost:5000/imprimir?created_date=2023-10-01&code=123456&services=Atendimento&header=Bem-vindo&footer=Obrigado")
    print("=============================================\n")

    serve(app,host='0.0.0.0', port=5000, threads=1)
