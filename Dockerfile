# 1. Etapa Base: Usamos una imagen oficial de Python como punto de partida.                                       
# 'slim' es más pequeño que la imagen completa, lo cual es bueno para la eficiencia.                              
FROM python:3.11-slim                                                                                             
                                                                                                                  
# 2. Configuración de Directorio de Trabajo:                                                                      
# Establece el directorio que se usará dentro del contenedor.                                                     
WORKDIR /app

# 3. Actualizar e instalar dependencias de sistema
# En Arch, systemd-libs provee los headers de udev necesarios para pyudev/serial
RUN apt-get update && \
    apt-get install -y --no-install-recommends\
    build-essential\
    libpq-dev \
    && apt-get clean\
    && rm -rf /var/lib/apt/lists/*
   
    
# 4. Copiar Dependencias:                                                                                         
# Copiamos primero el archivo requirements.txt. Esto es crucial para el cacheo de Docker.                         
# Si solo cambian otros archivos, Docker reutilizará esta capa de la imagen.                                      
COPY requirements.txt .                                                                                           
                                                                                                                    
# 5. Instalar Dependencias:                                                                                       
# Ejecuta pip para instalar todas las librerías listadas en el archivo.                                           
RUN pip install --no-cache-dir -r requirements.txt                                                                
                                                                                                                    
# 6. Copiar Código Fuente:                                                                                        
# Copiamos el resto de los archivos de la aplicación al directorio de trabajo.                                    
COPY . .                                                                                                          
                                                                                                                    
# 7. Definir Puerto de Exposición (Opcional pero recomendado):                                                    
# Informa al usuario qué puerto espera escuchar la aplicación.                                                    
EXPOSE 5000                                                                                                       
                                                                                                                    
# 8. Comando de Ejecución:                                                                                        
# Define el comando que se ejecutará cuando alguien corra 'docker run mi-imagen'.                                 
CMD ["python", "-m", "webapp.app"]   
