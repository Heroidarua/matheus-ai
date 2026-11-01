(() => {
  // Classificação local e determinística: não depende do Gemma adivinhar a intenção.
  const IMAGE_NOUN = String.raw`(?:imagem|figura|ilustra[cç][aã]o|arte|desenho|foto|retrato|paisagem|logo(?:tipo)?|banner|cartaz|p[oó]ster|capa|thumbnail|miniatura|avatar|wallpaper|papel de parede|[ií]cone|cena|picture|image|illustration|artwork)`;
  const CREATE_ACTION = String.raw`(?:crie?|criar|cria|gere?|gerar|gera|desenhe?|desenhar|desenha|ilustre?|ilustrar|produza|produzir|fa[cç]a|faz|monte|montar|elabore|elaborar|make|create|generate|draw|design)`;
  const EDIT_ACTION = String.raw`(?:transforme?|transformar|transforma|edite?|editar|edita|modifique?|modificar|modifica|altere?|alterar|altera|converta|converter|converte|estilize?|estilizar|estiliza|recrie?|recriar|recria|restaure?|restaurar|restaura|melhore?|melhorar|melhora|aperfei[cç]oe|remova|remover|retire|retirar|apague|apagar|adicione|adicionar|troque|trocar|substitua|substituir|recorte|recortar|remove|erase|edit|change|replace|turn|make me)`;
  const IMAGE_CONTEXT = String.raw`(?:foto|imagem|retrato|rosto|pessoa|fundo|cen[aá]rio|roupa|objeto|objeto|qualidade|resolu[cç][aã]o|luz|ilumina[cç][aã]o|cor|estilo|personagem|cartoon|anime|simpsons|pixar|disney|gibi|caricatura|background|photo|image|picture|face|object)`;
  const CREATE_RE = new RegExp(String.raw`\b${CREATE_ACTION}\b[\s\S]{0,100}\b${IMAGE_NOUN}\b|\b${IMAGE_NOUN}\b[\s\S]{0,80}\b${CREATE_ACTION}\b|\b(?:quero|preciso|gostaria)\b[\s\S]{0,55}\b(?:uma?\s+)?${IMAGE_NOUN}\b`, 'i');
  const EDIT_RE = new RegExp(String.raw`\b${EDIT_ACTION}\b[\s\S]{0,100}\b${IMAGE_CONTEXT}\b|\b(?:estilo|personagem|cartoon|anime|simpsons|pixar|disney|gibi|caricatura)\b|\b(?:remova|retire|apague|adicione|troque|substitua|melhore|aumente|restaure|recorte)\b`, 'i');

  function cleanPrompt(text) {
    return String(text || '').trim().replace(/\s+/g, ' ');
  }

  function extractImagePrompt(text) {
    const source = cleanPrompt(text);
    if (!source || !CREATE_RE.test(source)) return null;
    return source.replace(/^[\s,!.]*(?:por favor[,! ]*)?(?:quero que você|quero|preciso que você|pode|por favor)?[\s,!.]*/i, '') || source;
  }

  function extractImageEditPrompt(text) {
    const source = cleanPrompt(text);
    return source && EDIT_RE.test(source) ? source : null;
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
    const caption = document.createElement('p');
    caption.textContent = label;
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
    download.download = 'ada-m-imagem-' + Date.now() + (data.mime_type === 'image/jpeg' ? '.jpg' : '.png');
    download.textContent = '↓ Salvar imagem';
    actions.appendChild(download);
    bubble.appendChild(actions);
    bubble.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }

  window.ADAExtractImagePrompt = extractImagePrompt;
  window.ADAExtractImageEditPrompt = extractImageEditPrompt;

  window.ADAEditImageInChat = async (file, prompt, bubble) => {
    bubble.replaceChildren();
    const status = document.createElement('p');
    status.textContent = '🪄 Editando sua foto… A imagem original será usada como referência.';
    bubble.appendChild(status);
    const response = await fetch('/api/edit-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_data: await fileToBase64(file), mime_type: file.type, prompt })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível editar a foto.');
    renderResult(bubble, data, prompt, 'Foto editada pela ADA-M');
    return 'Foto editada com sucesso usando a imagem anexada como referência: ' + prompt;
  };

  window.ADAGenerateImageInChat = async (prompt, bubble) => {
    bubble.replaceChildren();
    const status = document.createElement('p');
    status.textContent = '🎨 Criando sua imagem… Isso pode levar alguns instantes.';
    bubble.appendChild(status);
    const style = /anime|mangá|japonês/i.test(prompt) ? 'anime'
      : /\b3d\b/i.test(prompt) ? '3d'
      : /minimalista/i.test(prompt) ? 'minimalista'
      : /ilustra[cç][aã]o|pintura digital/i.test(prompt) ? 'ilustracao'
      : 'realista';
    const response = await fetch('/api/generate-image', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, style })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Não foi possível gerar a imagem.');
    renderResult(bubble, data, prompt, 'Imagem criada pela ADA-M');
    return 'Imagem gerada com sucesso a partir do pedido: ' + prompt;
  };
})();