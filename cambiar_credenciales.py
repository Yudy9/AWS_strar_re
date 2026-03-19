#!/usr/bin/env python3
"""
Script para cambiar credenciales de AWS en ~/.aws/credentials.
Actualiza el perfil especificado con nuevas claves de acceso.
Uso: python cambiar_credenciales.py --access-key TU_ACCESS_KEY --secret-key TU_SECRET_KEY [--profile default] [--region us-east-1]
"""

import argparse
import configparser
import os
import sys
from pathlib import Path


def cambiar_credenciales(access_key: str, secret_key: str, profile: str = 'default', region: str = None, session_token: str = None) -> None:
    """
    Cambia las credenciales de AWS para el perfil especificado.
    """
    # Ruta al archivo de credenciales
    cred_file = Path.home() / '.aws' / 'credentials'
    
    # Crear directorio si no existe
    cred_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Leer archivo existente o crear uno nuevo
    config = configparser.ConfigParser()
    if cred_file.exists():
        config.read(cred_file)
    
    # Asegurar que el perfil existe
    if not config.has_section(profile):
        config.add_section(profile)
    
    # Actualizar credenciales
    config.set(profile, 'aws_access_key_id', access_key)
    config.set(profile, 'aws_secret_access_key', secret_key)
    
    # Actualizar región si se proporciona
    if region:
        config.set(profile, 'region', region)
    
    # Actualizar session token si se proporciona (para credenciales temporales)
    if session_token:
        config.set(profile, 'aws_session_token', session_token)
    else:
        # Si no se proporciona, eliminarlo si existe (para credenciales permanentes)
        if config.has_option(profile, 'aws_session_token'):
            config.remove_option(profile, 'aws_session_token')
    
    # Escribir de vuelta al archivo
    with open(cred_file, 'w') as f:
        config.write(f)
    
    # Cambiar permisos para que solo el propietario pueda leer/escribir
    cred_file.chmod(0o600)
    
    print(f"Credenciales actualizadas para el perfil '{profile}' en {cred_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Cambia las credenciales de AWS en ~/.aws/credentials."
    )
    parser.add_argument(
        '--access-key', '-a',
        required=True,
        help="Nueva AWS Access Key ID"
    )
    parser.add_argument(
        '--secret-key', '-s',
        required=True,
        help="Nueva AWS Secret Access Key"
    )
    parser.add_argument(
        '--profile', '-p',
        default='default',
        help="Perfil a actualizar (default: default)"
    )
    parser.add_argument(
        '--region', '-r',
        help="Región por defecto (opcional)"
    )
    parser.add_argument(
        '--session-token', '-t',
        help="AWS Session Token (para credenciales temporales, opcional)"
    )
    
    args = parser.parse_args()
    
    # Validación básica
    if not args.access_key or not args.secret_key:
        print("Error: Access Key y Secret Key son requeridos.")
        sys.exit(1)
    
    try:
        cambiar_credenciales(args.access_key, args.secret_key, args.profile, args.region, args.session_token)
        print("¡Credenciales cambiadas exitosamente!")
    except Exception as e:
        print(f"Error al cambiar credenciales: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()