# Seguridad

## Estado de la imagen publicada

`beta` y `latest` usan la compilación mitigada con digest `sha256:588a5bfbbc105612dc320e3f558b5a5145efd56601bb337d9b1d57e9ef0a31d5`. El inventario, las mitigaciones y los hallazgos residuales reconocidos se mantienen en [`docs/CVE-ACKNOWLEDGEMENTS.md`](docs/CVE-ACKNOWLEDGEMENTS.md).

`alpha` conserva intencionalmente una compilación histórica con vulnerabilidades conocidas y no debe desplegarse. Para instalaciones nuevas use `latest`; para despliegues críticos fije un digest que haya validado.

## Reporte responsable

No publique la interfaz HTTP directamente en Internet. Use HTTPS, restricción de red y una contraseña única. Los QR, archivos `.conf`, `state.db`, `wg0.conf` y backups contienen secretos.

Para reportar una vulnerabilidad, use [GitHub Security Advisories](https://github.com/aguilarbucket/Wireguard-GUI/security/advisories/new) o un canal privado del mantenedor. No abra un issue público con claves, configuraciones, endpoints ni logs completos. Incluya versión o digest, impacto, pasos mínimos de reproducción y una propuesta de mitigación cuando sea posible. Revoque inmediatamente cualquier cliente cuya clave haya sido expuesta.

## Modelo de privilegios

El despliegue soportado concede únicamente `NET_ADMIN`. Una solicitud de `privileged`, del socket Docker o de capabilities adicionales debe tratarse como un cambio de seguridad y justificarse por separado.
