#!/usr/bin/env python3
"""
Launcher Orchestrator Oficial - Extração de Legendas
Este script gerencia o ciclo de vida do Redis (WSL), Uvicorn (FastAPI) e Celery (Worker).
Possui recursos avançados de health-checking, port validation e graceful shutdown (anti-zombies).
"""

import sys
import os
import time
import socket
import signal
import subprocess
import threading
import psutil
from typing import List

# Cores para o terminal (NIST friendly log visibility)
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Configurações de Portas
PORTS_TO_CHECK = {
    "Redis": 6379,
    "FastAPI": 8000
}

# Comandos de Execução
# Utilizando o binário do python da venv local
if os.name == 'nt':
    PYTHON_BIN = os.path.join(".", "venv", "Scripts", "python.exe")
else:
    PYTHON_BIN = os.path.join(".", "venv", "bin", "python")

COMMANDS = {
    # Comando WSL para o Redis. Requer WSL configurado no Windows.
    "REDIS": ["wsl", "sudo", "service", "redis-server", "start"],
    # FastAPI Server
    "FASTAPI": [PYTHON_BIN, "-m", "uvicorn", "app.main:app", "--port", "8000"],
    # Celery Worker (pool=solo otimizado para Windows)
    "CELERY": [PYTHON_BIN, "-m", "celery", "-A", "app.workers.celery_worker", "worker", "--pool=solo", "-l", "info"]
}

# Variáveis globais para rastreamento de processos
active_processes: List[subprocess.Popen] = []
is_shutting_down = False

def log(prefix: str, message: str, color: str = Colors.ENDC):
    """Função thread-safe para output no console"""
    print(f"{color}{Colors.BOLD}[{prefix}]{Colors.ENDC} {message}")
    sys.stdout.flush()

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Verifica se uma porta de rede já está ocupada."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

def wait_for_port(port: int, service_name: str, host: str = "127.0.0.1", timeout: int = 30):
    """Bloqueia a execução até que a porta especificada esteja aceitando conexões."""
    start_time = time.time()
    log("SYSTEM", f"Aguardando o serviço {service_name} iniciar na porta {port}...", Colors.OKCYAN)
    while True:
        if is_port_in_use(port, host):
            log("SYSTEM", f"{service_name} está ONLINE na porta {port}.", Colors.OKGREEN)
            return True
        if time.time() - start_time > timeout:
            log("ERROR", f"Timeout aguardando o serviço {service_name} (Porta {port}).", Colors.FAIL)
            return False
        time.sleep(1)

def stream_reader(pipe, prefix: str, color: str):
    """Lê as saídas dos subprocessos assincronamente e direciona ao console formatado."""
    try:
        for line in iter(pipe.readline, b''):
            if is_shutting_down:
                break
            decoded_line = line.decode("utf-8", errors="replace").strip()
            if decoded_line:
                log(prefix, decoded_line, color)
    except Exception:
        pass

def start_process(name: str, cmd: List[str], prefix_color: str) -> subprocess.Popen:
    """Inicia um subprocesso de forma segura encapsulando stdout e stderr."""
    log("SYSTEM", f"Iniciando {name}...", Colors.OKBLUE)
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,  # Prevenção de bloqueios
        bufsize=1,
        universal_newlines=False,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    )
    
    active_processes.append(process)
    
    # Inicia a thread de leitura de logs
    t = threading.Thread(target=stream_reader, args=(process.stdout, name, prefix_color), daemon=True)
    t.start()
    
    return process

def terminate_process_tree(pid: int):
    """Mata a árvore inteira de processos de forma segura usando psutil (Anti-Zombie)"""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        # Termina as crianças primeiro
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        
        # Termina o pai
        parent.terminate()
        
        # Aguarda fim e força shutdown se necessário
        _, alive = psutil.wait_procs(children + [parent], timeout=3)
        for p in alive:
            try:
                p.kill()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        log("ERROR", f"Falha ao terminar árvore do processo {pid}: {e}", Colors.FAIL)

def shutdown_handler(signum, frame):
    """Captura o evento de fechamento da janela ou Ctrl+C para desligamento gracefully"""
    global is_shutting_down
    if is_shutting_down:
        return
        
    is_shutting_down = True
    log("SYSTEM", "\n[!] Sinal de interrupção recebido. Iniciando desligamento seguro (Graceful Shutdown)...", Colors.WARNING)
    
    # 1. Parar o Redis via WSL limpo
    log("SYSTEM", "Encerrando Redis-Server no WSL...", Colors.WARNING)
    try:
        subprocess.run(["wsl", "sudo", "service", "redis-server", "stop"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        log("ERROR", f"Não foi possível parar o Redis graciosamente: {e}", Colors.FAIL)

    # 2. Terminar arvore de processos ativos
    for p in active_processes:
        if p.poll() is None:
            terminate_process_tree(p.pid)
            
    log("SYSTEM", "Processos encerrados com sucesso. Sistema limpo.", Colors.OKGREEN)
    sys.exit(0)

def main():
    # Registra o hook de terminação/sinais de SO
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    if os.name == 'nt':
        signal.signal(signal.SIGBREAK, shutdown_handler)

    print(f"{Colors.HEADER}====================================================")
    print("   Orquestrador de Serviços - Fast Extração IA      ")
    print(f"===================================================={Colors.ENDC}\n")

    # 1. Verificação de Portas Preexistentes (Prevenção de Conflitos)
    for service, port in PORTS_TO_CHECK.items():
        if is_port_in_use(port):
            log("FATAL", f"A porta {port} já está em uso pelo sistema. O serviço {service} não pode iniciar.", Colors.FAIL)
            log("FATAL", "Por favor, encerre processos órfãos ou servidores que já estejam ocupando esta porta e tente novamente.", Colors.FAIL)
            sys.exit(1)

    try:
        # 2. Iniciar Redis (WSL)
        start_process("REDIS", COMMANDS["REDIS"], Colors.WARNING)
        if not wait_for_port(PORTS_TO_CHECK["Redis"], "Redis (WSL)"):
            sys.exit(1)
            
        # 3. Iniciar Uvicorn (FastAPI)
        start_process("FASTAPI", COMMANDS["FASTAPI"], Colors.OKCYAN)
        if not wait_for_port(PORTS_TO_CHECK["FastAPI"], "FastAPI Server"):
            terminate_process_tree(active_processes[-1].pid) # cleanup if failed
            sys.exit(1)

        # 4. Iniciar Celery Worker
        start_process("CELERY", COMMANDS["CELERY"], Colors.OKGREEN)
        
        # 5. Display Sucesso Prominente
        print("\n" + "="*50)
        print(f"{Colors.BOLD}{Colors.OKGREEN}🚀 TODOS OS SISTEMAS ESTÃO ONLINES E PRONTOS PARA USO!{Colors.ENDC}")
        print("="*50 + "\n")
        log("SYSTEM", "Aperte Ctrl+C nesta janela de terminal para desligar completamente e com segurança todo o sistema.", Colors.HEADER)

        # 6. Manter Orquestrador Vivo
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        # A interceptação principal ocorre no shutdown_handler via Signal, este except atua com fallback.
        pass
    except Exception as e:
        log("FATAL", f"Erro inesperado no Orquestrador: {str(e)}", Colors.FAIL)
        shutdown_handler(None, None)

if __name__ == "__main__":
    main()
