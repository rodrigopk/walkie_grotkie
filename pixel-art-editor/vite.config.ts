import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

function fileSavePlugin(): Plugin {
  const repoRoot = path.resolve(__dirname, '..')

  return {
    name: 'pixel-editor-file-save',
    configureServer(server) {
      server.middlewares.use('/__api/save-png', async (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405
          res.end('Method not allowed')
          return
        }

        const filePath = req.headers['x-file-path']
        if (typeof filePath !== 'string' || !filePath) {
          res.statusCode = 400
          res.end('Missing x-file-path header')
          return
        }

        const resolved = path.resolve(filePath)
        if (!resolved.startsWith(repoRoot + path.sep) && resolved !== repoRoot) {
          res.statusCode = 403
          res.end(`Path must be within the repository root (${repoRoot})`)
          return
        }

        const chunks: Buffer[] = []
        for await (const chunk of req) {
          chunks.push(Buffer.from(chunk))
        }
        const data = Buffer.concat(chunks)

        try {
          fs.mkdirSync(path.dirname(resolved), { recursive: true })
          fs.writeFileSync(resolved, data)
          res.statusCode = 200
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify({ ok: true, path: resolved, bytes: data.length }))
        } catch (err) {
          res.statusCode = 500
          res.end(String(err))
        }
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), fileSavePlugin()],
})
