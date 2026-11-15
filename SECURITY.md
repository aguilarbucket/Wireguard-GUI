# Seguridad

No publique la interfaz HTTP directamente en Internet. Use HTTPS, restricción de red y una contraseña única. Los QR, archivos `.conf`, `state.db`, `wg0.conf` y backups contienen secretos.

Para reportar una vulnerabilidad, use un canal privado del mantenedor y no abra un issue público con claves, configuraciones, endpoints ni logs completos. Revoque inmediatamente cualquier cliente cuya clave haya sido expuesta.

El despliegue soportado concede únicamente `NET_ADMIN`. Una solicitud de `privileged`, del socket Docker o de capabilities adicionales debe tratarse como un cambio de seguridad y justificarse por separado.
