docker run -d -p 9100:9100 \
  --net="host" \
  --pid="host" \
  -v "/proc:/host/proc:ro" \
  -v "/sys:/host/sys:ro" \
  -v "/:/host:ro,rslave" \
  node_exporter \
  --path.rootfs=/host
