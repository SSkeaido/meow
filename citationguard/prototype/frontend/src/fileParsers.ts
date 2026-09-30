function normalizeText(value: string) {
  return value
    .replace(/\r\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

async function extractPdfText(file: File) {
  const [{ GlobalWorkerOptions, getDocument }, { default: pdfWorkerUrl }] = await Promise.all([
    import('pdfjs-dist'),
    import('pdfjs-dist/build/pdf.worker.min.mjs?url'),
  ])
  GlobalWorkerOptions.workerSrc = pdfWorkerUrl
  const buffer = await file.arrayBuffer()
  const pdf = await getDocument({ data: new Uint8Array(buffer) }).promise
  const pages: string[] = []

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
    const page = await pdf.getPage(pageNumber)
    const textContent = await page.getTextContent()
    const text = textContent.items
      .map((item) => ('str' in item ? item.str : ''))
      .join(' ')
      .trim()

    if (text) {
      pages.push(text)
    }
  }

  const combined = normalizeText(pages.join('\n\n'))
  if (!combined) {
    throw new Error('这个 PDF 没有可提取文字，可能是扫描件。当前前端原型暂不支持扫描件 OCR。')
  }

  return combined
}

async function extractDocxText(file: File) {
  const { default: mammoth } = await import('mammoth')
  const buffer = await file.arrayBuffer()
  const result = await mammoth.extractRawText({ arrayBuffer: buffer })
  return normalizeText(result.value)
}

export async function extractTextFromFile(file: File) {
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''

  if (ext === 'pdf') {
    return extractPdfText(file)
  }

  if (ext === 'docx') {
    return extractDocxText(file)
  }

  if (ext === 'txt' || ext === 'md' || ext === 'markdown') {
    return normalizeText(await file.text())
  }

  throw new Error('当前前端原型支持 PDF、DOCX、TXT、MD。旧版 DOC 可以后续再补。')
}
