(() => {
  const IMAGE_INTENT = /\b(?:crie|criar|cria|gere|gerar|gera|desenhe|desenhar|desenha|ilustre|ilustrar|produza|produzir|fa[cç]a|faz|make|create|generate|draw)\b.{0,45}\b(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\b|\b(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\b.{0,35}\b(?:crie|criar|cria|gere|gerar|gera|desenhe|desenhar|ilustre|produza|fa[cç]a|make|create|generate|draw)\b/i;
  const IMAGE_EDIT_INTENT = /\b(?:transforme|transformar|transforma|transform|edite|editar|edita|modifique|modificar|modifica|converta|converter|estilize|estilizar|recrie|recriar|vire|turn\s+me\s+into|make\s+me)\b|\b(?:estilo|personagem|cartoon|desenho|anime|simpsons|pixar|disney|gibi|caricatura)\b/i;
  function extractImagePrompt(text) {
    const source = String(text || '').trim();
    if (!source || !IMAGE_INTENT.test(source)) return null;
    let prompt = source.replace(/^\s*(?:por favor[,! ]*)?(?:pode\s+)?(?:crie|criar|cria|gere|gerar|gera|desenhe|desenhar|desenha|ilustre|ilustrar|produza|produzir|fa[cç]a|faz|make|create|generate|draw)\s+(?:para\s+mim\s+)?/i, '')
      .replace(/^\s*(?:uma?\s+)?(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\s+(?:de|do|da|dos|das|about|of)\s+/i, '')
      .replace(/^\s*(?:uma?\s+)?(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\s*/i, '')
      .replace(/^\s*(?:de|do|da|dos|das|of)\s+/i, '').trim();
    return prompt.length >= 3 ? prompt : source;
  }
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(',')[1] || '');
      reader.onerror = () => reject(new Error('Não foi possível ler a foto anexada.'));
      reader.readAsDataURL(file);
    });
  }
  function renderResult(bubble, data, prompt, label) {
    if (!data.image_data || !data.mime_type) throw new Error('O serviço não retornou uma imagem válida.');
    const dataUrl = 'data:' + data.mime_type + ';base64,' + data.image_data;
    bubble.replaceChildren();
    const caption = document.createElement('p'); caption.textContent = label; bubble.appendChild(caption);
    const image = document.createElement('img'); image.className = 'generated-image'; image.alt = prompt; image.loading = 'lazy'; image.src = dataUrl; bubble.appendChild(image);
    const actions = document.createElement('div'); actions.className = 'generated-image-actions';
    const download = document.createElement('a'); download.className = 'image-download'; download.href = dataUrl; download.download = 'ada-m-imagem-' + Date.now() + '.png'; download.textContent = '↓ Salvar imagem';
    actions.appendChild(download); bubble.appendChild(actions); bubble.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
  window.ADAExtractImagePrompt = extractImagePrompt;
  window.ADAExtractImageEditPrompt = text => {
    const source = String(text || '').trim();
    return source && IMAGE_EDIT_INTENT.test(source) ? source : null;
  };
  window.ADAEditImageInChat = async (file, prompt, bubble) => {
    bubble.replaceChildren();
    const status = document.createElement('p'); status.textContent = '🪄 Transformando sua foto… Isso pode levar alguns instantes.'; bubble.appendChild(status);
    const response = await fetch('/api/edit-image', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ image_data: await fileToBase64(file), mime_type: file.type, prompt }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível editar a foto.');
    renderResult(bubble, data, prompt, 'Foto transformada pela ADA-M');
    return 'Foto transformada com sucesso usando a imagem anexada como referência: ' + prompt;
  };
  window.ADAGenerateImageInChat = async (prompt, bubble) => {
    bubble.replaceChildren();
    const status = document.createElement('p'); status.textContent = '🎨 Criando sua imagem… Isso pode levar alguns instantes.'; bubble.appendChild(status);
    const response = await fetch('/api/generate-image', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt, style: /anime|mangá|japonês/i.test(prompt) ? 'anime' : /\b3d\b/i.test(prompt) ? '3d' : /minimalista/i.test(prompt) ? 'minimalista' : /ilustração|pintura digital/i.test(prompt) ? 'ilustracao' : 'realista' }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível gerar a imagem.');
    renderResult(bubble, data, prompt, 'Imagem criada pela ADA-M');
    return 'Imagem gerada com sucesso a partir do pedido: ' + prompt;
  };
})();
