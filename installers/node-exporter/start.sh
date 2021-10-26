docker run -d -p 9100:9100 \
  --net="host" \
  --pid="host" \
  -v "/proc:/host/proc:ro" \
  -v "/sys:/host/sys:ro" \
  -v "/:/host:ro,rslave" \
  --log-opt max-size=10m --log-opt max-file=10 \
  node_exporter \
  --path.rootfs=/host
