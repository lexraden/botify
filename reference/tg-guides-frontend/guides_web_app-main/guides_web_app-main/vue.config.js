module.exports = {
  devServer: {
    allowedHosts: ['.ledokol.it'],
    host: '0.0.0.0',
    port: 8081,
    headers: {
      'Access-Control-Allow-Origin': '*'
    }
  }
}
