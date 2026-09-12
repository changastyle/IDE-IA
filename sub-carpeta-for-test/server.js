// Servidor estático simple para el juego Snake
// Uso: node server.js  (o: node server.js 3000)

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || process.argv[2] || 3000;
const ROOT = __dirname;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8'
};

const server = http.createServer((req, res) => {
  // Normalizar la ruta solicitada
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  if (urlPath === '/') urlPath = '/index.html';

  const filePath = path.join(ROOT, path.normalize(urlPath));

  // Seguridad: evitar salir de la carpeta del proyecto
  if (!filePath.startsWith(ROOT)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' });
    return res.end('403 - Prohibido');
  }

  fs.stat(filePath, (err, stats) => {
    if (!err && stats.isDirectory()) {
      // Si es una carpeta, intentar servir su index.html
      return serveFile(path.join(filePath, 'index.html'));
    }
    serveFile(filePath, err);
  });

  function serveFile(file, statErr) {
    fs.readFile(file, (err, data) => {
      if (err) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
        return res.end('404 - No encontrado: ' + urlPath);
      }
      const ext = path.extname(file).toLowerCase();
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
      res.end(data);
    });
  }
});

server.listen(PORT, () => {
  console.log(`🐍 Servidor del Snake corriendo en http://localhost:${PORT}`);
  console.log('   Abre index.html o snake.html en tu navegador.');
});
