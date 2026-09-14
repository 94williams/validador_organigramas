#!/bin/bash
# ============================================================
# Arranca el Validador de Organigramas para acceso en red local.
#
# Uso normal:
#     ./start_server.sh
#
# Cambiar el puerto (por defecto 8501):
#     VALIDADOR_PORT=9000 ./start_server.sh
#
# Proteger con contraseña (recomendado si compartes fuera de tu
# red local, ej. con Tailscale):
#     VALIDADOR_PASSWORD=una-clave-segura ./start_server.sh
# ============================================================

PUERTO="${VALIDADOR_PORT:-8501}"

echo ""
echo "============================================================"
echo "  Validador de Organigramas"
echo "============================================================"
echo "  Se iniciará en el puerto $PUERTO"
echo ""
echo "  Acceso desde ESTA máquina:"
echo "    http://localhost:$PUERTO"
echo ""
echo "  Acceso desde OTRAS máquinas en tu red local (oficina):"
IP_LOCAL=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -n "$IP_LOCAL" ]; then
  echo "    http://$IP_LOCAL:$PUERTO"
else
  echo "    Corre 'ifconfig' o 'ip addr' para encontrar tu IP local, luego:"
  echo "    http://TU-IP-LOCAL:$PUERTO"
fi
echo ""
echo "  Para acceso desde FUERA de la red local, ve la sección"
echo "  \"Acceso remoto\" del README (Tailscale recomendado)."
echo "============================================================"
echo ""

streamlit run ui/app.py --server.address 0.0.0.0 --server.port "$PUERTO"
