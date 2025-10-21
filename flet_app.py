import flet as ft
import subprocess
import threading
import sys
import os
import signal
import time
import requests


class ServerProcess:
    def __init__(self, script_path):
        self.script_path = script_path
        self.process = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self.process and self.process.poll() is None:
                return
            python_exe = sys.executable
            self.process = subprocess.Popen(
                [python_exe, self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )

    def stop(self):
        with self._lock:
            if not self.process:
                return
            if os.name == "nt":
                try:
                    self.process.send_signal(signal.CTRL_BREAK_EVENT)
                except Exception:
                    self.process.terminate()
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None


def main(page: ft.Page):
    page.title = "Cliente de Impressão - Monitor"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.window_width = 980
    page.window_height = 720
    page.theme_mode = ft.ThemeMode.LIGHT

    script_path = os.path.join(os.getcwd(), "printer_app.py")
    server = ServerProcess(script_path)

    log_view = ft.ListView(expand=True, spacing=4, auto_scroll=True)

    status_badge = ft.Chip(label=ft.Text("Parado"), color=ft.Colors.RED_400)

    def append_log(line, level="INFO"):
        # Exibir no terminal também
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {line.rstrip()}")
        
        color = ft.Colors.BLUE_800 if level == "INFO" else ft.Colors.RED_700
        log_view.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text(level, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        padding=ft.padding.symmetric(3, 2),
                        bgcolor=color,
                        border_radius=4,
                    ),
                    ft.Text(line.rstrip(), selectable=True),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        page.update()

    stop_flag = threading.Event()

    def reader_loop():
        while not stop_flag.is_set():
            if server.is_running() and server.process.stdout:
                line = server.process.stdout.readline()
                if line:
                    level = "ERROR" if "ERROR" in line or "Traceback" in line else "INFO"
                    append_log(line, level=level)
                else:
                    time.sleep(0.05)
            else:
                time.sleep(0.2)

    reader_thread = threading.Thread(target=reader_loop, daemon=True)
    reader_thread.start()

    def handle_start(e):
        if not os.path.exists(script_path):
            append_log("printer_app.py não encontrado no diretório atual.", level="ERROR")
            return
        append_log("Iniciando servidor Flask...", level="INFO")
        server.start()
        status_badge.label = ft.Text("Em execução")
        status_badge.color = ft.Colors.GREEN_400
        append_log("Servidor Flask iniciado com sucesso!", level="INFO")
        page.update()

    def handle_stop(e):
        append_log("Parando servidor Flask...", level="INFO")
        server.stop()
        status_badge.label = ft.Text("Parado")
        status_badge.color = ft.Colors.RED_400
        append_log("Servidor Flask parado.", level="INFO")
        page.update()

    def call_endpoint(path, params=None):
        url = f"http://localhost:5000{path}"
        append_log(f"Chamando endpoint: {url}", level="INFO")
        if params:
            append_log(f"Parâmetros: {params}", level="INFO")
        try:
            r = requests.get(url, params=params or {}, timeout=10)
            append_log(f"Resposta: {r.status_code} {r.text}")
        except Exception as ex:
            append_log(f"Falha ao chamar {url}: {ex}", level="ERROR")

    header = ft.TextField(label="Cabeçalho", value="Bem-vindo")
    footer = ft.TextField(label="Rodapé", value="Obrigado")
    code = ft.TextField(label="Código", value="A123")
    services = ft.TextField(label="Serviços", value="Atendimento")
    created_date = ft.TextField(label="Data", value="2025-01-01")
    qrcode_value = ft.TextField(label="QR Code (conteúdo)", value="https://exemplo.com")

    def handle_test_print(e):
        params = {
            "created_date": created_date.value,
            "code": code.value,
            "services": services.value,
            "header": header.value,
            "footer": footer.value,
        }
        call_endpoint("/imprimir", params)

    def handle_test_qr(e):
        params = {
            "created_date": created_date.value,
            "code": code.value,
            "services": services.value,
            "header": header.value,
            "footer": footer.value,
            "qrcode": qrcode_value.value,
        }
        call_endpoint("/imprimir/qrcode", params)

    controls_bar = ft.Row(
        [
            ft.ElevatedButton("Iniciar servidor", icon=ft.Icons.PLAY_ARROW, on_click=handle_start),
            ft.OutlinedButton("Parar servidor", icon=ft.Icons.STOP, on_click=handle_stop),
            status_badge,
            ft.Container(expand=True),
            ft.FilledTonalButton("Testar impressão", icon=ft.Icons.PRINT, on_click=handle_test_print),
            ft.FilledTonalButton("Testar QRCode", icon=ft.Icons.QR_CODE_2, on_click=handle_test_qr),
        ],
        alignment=ft.MainAxisAlignment.START,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    form = ft.ResponsiveRow(
        [
            ft.Container(header, col=6),
            ft.Container(footer, col=6),
            ft.Container(code, col=4),
            ft.Container(services, col=4),
            ft.Container(created_date, col=4),
            ft.Container(qrcode_value, col=12),
        ],
        run_spacing=10,
        alignment=ft.MainAxisAlignment.START,
    )

    page.add(
        ft.Column(
            [
                controls_bar,
                ft.Card(ft.Container(content=form, padding=12)),
                ft.Card(ft.Container(content=log_view, padding=0, expand=True)),
            ],
            expand=True,
            spacing=10,
        )
    )
    
    # Log inicial
    append_log("=== Cliente de Impressão de Senhas ===", level="INFO")
    append_log("Interface Flet carregada. Use os controles acima para gerenciar o servidor.", level="INFO")

    def on_close(e):
        stop_flag.set()
        try:
            server.stop()
        finally:
            page.window_destroy()

    page.on_window_event = lambda e: on_close(e) if e.data == "close" else None


if __name__ == "__main__":
    ft.app(target=main)


