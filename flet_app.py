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
    advanced_log_view = ft.ListView(expand=True, spacing=4, auto_scroll=True)
    
    # Toggle para logs simples/avançados
    show_advanced_logs = ft.Ref[ft.Switch]()
    current_log_view = ft.Ref[ft.Container]()
    
    status_badge = ft.Chip(label=ft.Text("Parado"), color=ft.Colors.RED_400)

    def append_simple_log(message, status="success"):
        """Adiciona log simplificado para o usuário"""
        icon = ft.Icons.CHECK_CIRCLE if status == "success" else ft.Icons.ERROR if status == "error" else ft.Icons.INFO
        color = ft.Colors.GREEN_600 if status == "success" else ft.Colors.RED_600 if status == "error" else ft.Colors.BLUE_600
        
        log_view.controls.append(
            ft.Row(
                [
                    ft.Icon(icon, color=color, size=20),
                    ft.Text(message, size=14, weight=ft.FontWeight.W_500),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        page.update()

    def append_advanced_log(line, level="INFO"):
        """Adiciona log técnico detalhado"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {line.rstrip()}")
        
        color = ft.Colors.BLUE_800 if level == "INFO" else ft.Colors.RED_700
        advanced_log_view.controls.append(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Text(level, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        padding=ft.padding.symmetric(3, 2),
                        bgcolor=color,
                        border_radius=4,
                    ),
                    ft.Text(line.rstrip(), selectable=True, size=12),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        page.update()

    def append_log(line, level="INFO"):
        """Função principal que decide qual tipo de log usar"""
        # Sempre adiciona ao log avançado
        append_advanced_log(line, level)
        
        # Adiciona ao log simples apenas se for relevante para o usuário
        if "Servidor Flask iniciado com sucesso" in line:
            append_simple_log("✅ Servidor iniciado com sucesso", "success")
        elif "Servidor Flask parado" in line:
            append_simple_log("⏹️ Servidor parado", "info")
        elif "Resposta: 200 Imprimindo" in line:
            append_simple_log("✅ Senha impressa com sucesso na impressora", "success")
        elif "Resposta: 200" in line and "Imprimindo" in line:
            append_simple_log("✅ Senha enviada para impressora com sucesso", "success")
        elif "Erro ao imprimir" in line or "Falha ao chamar" in line:
            append_simple_log("❌ Falha ao enviar senha para impressora", "error")
        elif "HTTPConnectionPool" in line or "Failed to establish" in line:
            append_simple_log("❌ Servidor não está respondendo", "error")
        elif "ERROR" in line or "Traceback" in line:
            append_simple_log("⚠️ Erro no sistema", "error")

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

    def auto_start_server():
        """Inicia o servidor automaticamente"""
        if not os.path.exists(script_path):
            append_log("printer_app.py não encontrado no diretório atual.", level="ERROR")
            return
        append_log("Iniciando servidor Flask automaticamente...", level="INFO")
        server.start()
        status_badge.label = ft.Text("Em execução")
        status_badge.color = ft.Colors.GREEN_400
        append_log("Servidor Flask iniciado com sucesso!", level="INFO")
        page.update()

    def toggle_logs(e):
        """Alterna entre logs simples e avançados"""
        if show_advanced_logs.current.value:
            # Mostrar logs avançados
            current_log_view.current.content = advanced_log_view
            current_log_view.current.bgcolor = ft.Colors.GREY_100
        else:
            # Mostrar logs simples
            current_log_view.current.content = log_view
            current_log_view.current.bgcolor = ft.Colors.WHITE
        page.update()

    def call_endpoint(path, params=None):
        url = f"http://localhost:5000{path}"
        append_log(f"Chamando endpoint: {url}", level="INFO")
        if params:
            append_log(f"Parâmetros: {params}", level="INFO")
        
        # Log específico para impressão
        if "/imprimir" in path:
            if "/qrcode" in path:
                append_simple_log("📤 Enviando senha com QR Code para impressora...", "info")
            else:
                append_simple_log("📤 Enviando senha para impressora...", "info")
        
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

    # Toggle de logs
    log_toggle = ft.Row(
        [
            ft.Text("Logs Simples", size=12),
            ft.Switch(
                ref=show_advanced_logs,
                on_change=toggle_logs,
                value=False,
                active_color=ft.Colors.BLUE_600,
            ),
            ft.Text("Logs Avançados", size=12),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    controls_bar = ft.Row(
        [
            ft.Text("🖥️ Servidor Flask", size=16, weight=ft.FontWeight.BOLD),
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

    # Container de logs com toggle
    log_container = ft.Container(
        content=log_view,
        ref=current_log_view,
        padding=12,
        expand=True,
        bgcolor=ft.Colors.WHITE,
    )

    page.add(
        ft.Column(
            [
                controls_bar,
                ft.Card(ft.Container(content=form, padding=12)),
                ft.Card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text("📋 Logs do Sistema", size=16, weight=ft.FontWeight.BOLD),
                                    ft.Container(expand=True),
                                    log_toggle,
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Divider(height=1),
                            log_container,
                        ],
                        expand=True,
                        spacing=0,
                    ),
                    expand=True,
                ),
            ],
            expand=True,
            spacing=10,
        )
    )
    
    # Log inicial e início automático do servidor
    append_log("=== Cliente de Impressão de Senhas ===", level="INFO")
    append_log("Interface Flet carregada. Iniciando servidor automaticamente...", level="INFO")
    
    # Inicia o servidor automaticamente após um pequeno delay
    def delayed_start():
        time.sleep(1)  # Aguarda 1 segundo para a interface carregar
        auto_start_server()
    
    threading.Thread(target=delayed_start, daemon=True).start()

    def on_close(e):
        stop_flag.set()
        try:
            server.stop()
        finally:
            page.window_destroy()

    page.on_window_event = lambda e: on_close(e) if e.data == "close" else None


if __name__ == "__main__":
    ft.app(target=main)


