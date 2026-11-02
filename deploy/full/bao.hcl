# Dedicated synthetic laboratory only. Use approved TLS/unseal/HSM controls in production.
ui = true
api_addr = "http://bao:8200"
cluster_addr = "http://bao:8201"
storage "raft" {
  path = "/openbao/data"
  node_id = "fabric-lab"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = true
}
