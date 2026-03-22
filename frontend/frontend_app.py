import streamlit as st
import requests
import time
import os
import logging

# Configuração de Log no Client-Side
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FrontendApp")

# Configurações do Backend e da Aplicação
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/api/v1")
MAX_UPLOAD_SIZE = 1 * 1024 * 1024 * 1024  # 1GB em bytes
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
ALLOWED_MIME_TYPES = {"video/mp4", "video/x-msvideo", "video/quicktime", "video/x-matroska"}

# Configuração da Página Streamlit
st.set_page_config(
    page_title="Gerador de Legendas Seguro",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Custom CSS para UI/UX mais limpa e moderna
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    h1 {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1f2937;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .stAlert {
        border-radius: 8px;
    }
    .upload-text {
        text-align: center;
        color: #6b7280;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def validate_client_side(file) -> bool:
    """Realiza validação de segurança no client-side antes do envio."""
    if file is None:
        return False
        
    # Validar tamanho
    if file.size > MAX_UPLOAD_SIZE:
        st.error(f"⚠️ O arquivo excede o limite máximo de 1GB. Tamanho atual: {file.size / (1024*1024):.2f} MB")
        logger.warning(f"Tentativa de upload de arquivo muito grande: {file.name} ({file.size} bytes)")
        return False
        
    # Validar extensão
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        st.error(f"⚠️ Extensão não permitida: {ext}. Formatos aceitos: {', '.join(ALLOWED_EXTENSIONS)}")
        logger.warning(f"Tentativa de upload com extensão inválida: {file.name}")
        return False
        
    # Validar MIME type básico fornecido pelo browser/Streamlit
    if file.type not in ALLOWED_MIME_TYPES and not file.type.startswith('video/'):
        st.error(f"⚠️ Tipo de arquivo não suportado: {file.type}. Por favor, envie um vídeo válido.")
        logger.warning(f"Tentativa de upload com MIME type inválido: {file.type}")
        return False
        
    return True

def upload_video(file):
    """Realiza o upload do vídeo para o backend via HTTP POST."""
    url = f"{BACKEND_URL}/upload-video"
    files = {"file": (file.name, file, file.type)}
    
    try:
        response = requests.post(url, files=files, timeout=30)
        
        # Tratamento seguro de erros HTTP
        if response.status_code == 413:
            st.error("❌ O servidor recusou o arquivo por ser muito grande (Payload Too Large).")
            return None
        elif response.status_code == 422:
            st.error("❌ Os dados enviados estavam em um formato inválido (Unprocessable Entity).")
            return None
        elif response.status_code == 400:
            st.error("❌ Requisição inválida (Bad Request). Verifique o formato do arquivo.")
            return None
        elif response.status_code >= 500:
            st.error("🔌 Erro interno no servidor ou fila offline. Tente novamente mais tarde.")
            logger.error(f"Erro do servidor: Status {response.status_code}")
            return None
            
        response.raise_for_status()
        data = response.json()
        logger.info(f"Upload bem sucedido. Job ID: {data.get('job_id')}")
        return data.get("job_id")
        
    except requests.exceptions.Timeout:
        st.error("⏱️ Tempo limite de conexão excedido ao enviar o vídeo.")
        logger.error("Timeout ao realizar upload.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 Falha na conexão com o servidor. Verifique se o backend está online.")
        logger.error("Falha de conexão ao backend.")
        return None
    except Exception as e:
        st.error("❌ Ocorreu um erro inesperado durante o envio.")
        logger.error(f"Erro inesperado no upload: {str(e)}")
        return None

def main():
    st.markdown("<h1>🎬 Extração Automática de Legendas</h1>", unsafe_allow_html=True)
    st.markdown("<p class='upload-text'>Faça upload do seu vídeo e o sistema gerará as legendas (SRT) utilizando Inteligência Artificial de ponta.</p>", unsafe_allow_html=True)

    # Inicializa estado da sessão se não existir
    if "job_id" not in st.session_state:
        st.session_state.job_id = None
    if "status" not in st.session_state:
        st.session_state.status = None
    if "original_filename" not in st.session_state:
        st.session_state.original_filename = "legenda"

    # Zona de Upload (Drag and Drop nativo do Streamlit)
    uploaded_file = st.file_uploader(
        "Arraste e solte o vídeo aqui", 
        type=["mp4", "avi", "mov", "mkv"],
        help="Limite de 1GB. Formatos aceitos: .mp4, .avi, .mov, .mkv"
    )

    if uploaded_file is not None and st.session_state.job_id is None:
        if st.button("🚀 Iniciar Processamento", type="primary", use_container_width=True):
            if validate_client_side(uploaded_file):
                with st.spinner("Enviando vídeo para o servidor..."):
                    job_id = upload_video(uploaded_file)
                    if job_id:
                        st.session_state.job_id = job_id
                        st.session_state.status = "PENDING"
                        st.session_state.original_filename = os.path.splitext(uploaded_file.name)[0]
                        st.rerun()

    # Mecanismo de Polling e Feedback de Progresso
    if st.session_state.job_id:
        st.divider()
        st.markdown(f"**ID do Trabalho:** `{st.session_state.job_id}`")
        
        status_container = st.empty()
        progress_bar = st.progress(0)
        
        job_id = st.session_state.job_id
        url = f"{BACKEND_URL}/status/{job_id}"
        
        # Long Polling Loop
        while st.session_state.status not in ["SUCCESS", "FAILURE"]:
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get("status", "UNKNOWN")
                    progress = data.get("progress", 0)
                    
                    st.session_state.status = status
                    
                    # Atualiza a UI em Tempo Real
                    progress_bar.progress(progress / 100.0)
                    
                    if status == "PENDING" or progress == 0:
                        status_container.info("⏳ Aguardando na fila...")
                    elif progress < 100 and not status.startswith("Erro"):
                        status_container.warning(f"⚙️ Processando vídeo... ({progress}%) - Isso pode levar alguns minutos.")
                    elif progress == 100 or status == "Completed" or status == "SUCCESS":
                        progress_bar.progress(1.0)
                        status_container.success("✅ Legenda gerada com sucesso!")
                        st.session_state.status = "SUCCESS"  # Força o status para disparar a área de Download
                        break
                    elif status.startswith("Erro") or status == "FAILURE":
                        error_msg = data.get("error", "Erro desconhecido")
                        status_container.error("❌ Falha no processamento do vídeo.")
                        st.error(f"Detalhes seguros: Ocorreu um erro no worker. O processamento foi interrompido.")
                        logger.error(f"Job {job_id} falhou: {error_msg}")
                        st.session_state.status = "FAILURE"
                        break
                else:
                    status_container.error("⚠️ Não foi possível obter o status. Tentando novamente...")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro no polling de status: {str(e)}")
                status_container.error("🔌 Perda de conexão com o servidor. Aguarde, tentando reconectar...")
                
            time.sleep(2)

        # Download Seguro
        if st.session_state.status == "SUCCESS":
            st.divider()
            download_url = f"{BACKEND_URL}/download/{job_id}"
            
            try:
                with st.spinner("Preparando arquivo para download..."):
                    # Fazemos a requisição para pegar os bytes do arquivo para o botão de download do Streamlit
                    dl_response = requests.get(download_url, timeout=15)
                    
                    if dl_response.status_code == 200:
                        srt_bytes = dl_response.content
                        st.success("🎉 O arquivo de legenda (.srt) está pronto!")
                        
                        if st.button("📁 Escolher Pasta e Salvar Legenda (.srt)", type="primary", use_container_width=True):
                            import tkinter as tk
                            from tkinter import filedialog
                            
                            try:
                                root = tk.Tk()
                                root.withdraw()
                                root.wm_attributes('-topmost', 1)
                                
                                file_path = filedialog.asksaveasfilename(
                                    initialfile=f"{st.session_state.original_filename}.srt",
                                    defaultextension=".srt",
                                    filetypes=[("Legendas SRT", "*.srt"), ("Todos os Arquivos", "*.*")]
                                )
                                root.destroy()
                                
                                if file_path:
                                    with open(file_path, "wb") as f:
                                        f.write(srt_bytes)
                                    st.success(f"✅ Arquivo salvo com sucesso em: {file_path}")
                                else:
                                    st.warning("⚠️ Salvamento cancelado.")
                            except Exception as e:
                                st.error(f"❌ Erro ao abrir janela de seleção: {str(e)}")
                                
                    elif dl_response.status_code == 404:
                        st.error("❌ Arquivo não encontrado no servidor.")
                    else:
                        st.error("❌ Erro ao tentar estabelecer download seguro.")
            except requests.exceptions.RequestException:
                st.error("🔌 Falha na conexão ou tempo limite esgotado ao tentar baixar o arquivo.")

        # Botão para Novo Envio
        if st.button("🔄 Novo Processamento", use_container_width=True):
            st.session_state.job_id = None
            st.session_state.status = None
            st.session_state.original_filename = "legenda"
            st.rerun()

if __name__ == "__main__":
    main()
