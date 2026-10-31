(() => {
  const IMAGE_INTENT = /\b(?:crie|criar|cria|gere|gerar|gera|desenhe|desenhar|desenha|ilustre|ilustrar|produza|produzir|fa[cç]a|faz|make|create|generate|draw)\b.{0,45}\b(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\b|\b(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\b.{0,35}\b(?:crie|criar|cria|gere|gerar|gera|desenhe|desenhar|ilustre|produza|fa[cç]a|make|create|generate|draw)\b/i;

  function extractImagePrompt(text) {
    const source = String(text || '').trim();
    if (!source || !IMAGE_INTENT.test(source)) return null;
    let prompt = source
      .replace(/^\s*(?:por favor[,! ]*)?(?:pode\s+)?(?:crie|criar|cria|gere|gerar|gera|desenhe|desenhar|desenha|ilustre|ilustrar|produza|produzir|fa[cç]a|faz|make|create|generate|draw)\s+(?:para\s+mim\s+)?/i, '')
      .replace(/^\s*(?:uma?\s+)?(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\s+(?:de|do|da|dos|das|about|of)\s+/i, '')
      .replace(/^\s*(?:uma?\s+)?(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|picture|image|illustration|artwork)\s*/i, '')
      .replace(/^\s*(?:de|do|da|dos|das|of)\s+/i, '')
      .trim();
    return prompt.length >= 3 ? prompt : source;
  }

  function chooseStyle(prompt) {
    const text = prompt.toLowerCase();
    if (/\banime|mang[aá]|japon[eê]s\b/.test(text)) return 'anime';
    if (/\b3d|tr[eê]s dimens[oõ]es|renderiza[cç][aã]o 3d\b/.test(text)) return '3d';
    if (/\bminimalista|minimalism\b/.test(text)) return 'minimalista';
    if (/\bilustra[cç][aã]o|ilustrado|pintura digital|concept art\b/.test(text)) return 'ilustracao';
    return 'realista';
  }

  window.ADAExtractImagePrompt = extractImagePrompt;
  window.ADAGenerateImageInChat = async (prompt, bubble) => {
    bubble.replaceChildren();
    const status = document.createElement('p');
    status.textContent = '🎨 Criando sua imagem… Isso pode levar alguns instantes.';
    bubble.appendChild(status);

    const response = await fetch('/api/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, style: chooseStyle(prompt) })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível gerar a imagem.');
    if (!data.image_data || !data.mime_type) throw new Error('O serviço não retornou uma imagem válida.');

    const dataUrl = 'data:' + data.mime_type + ';base64,' + data.image_data;
    bubble.replaceChildren();
    const caption = document.createElement('p');
    caption.textContent = 'Imagem criada pela ADA-M';
    bubble.appendChild(caption);

    const image = document.createElement('img');
    image.className = 'generated-image';
    image.alt = prompt;
    image.loading = 'lazy';
    image.src = dataUrl;
    bubble.appendChild(image);

    const actions = document.createElement('div');
    actions.className = 'generated-image-actions';
    const download = document.createElement('a');
    download.className = 'image-download';
    download.href = dataUrl;
    download.download = 'ada-m-imagem-' + Date.now() + '.png';
    download.textContent = '↓ Salvar imagem';
    actions.appendChild(download);
    bubble.appendChild(actions);
    bubble.scrollIntoView({ behavior: 'smooth', block: 'end' });
    return 'Imagem gerada com sucesso a partir do pedido: ' + prompt;
  };
})();
