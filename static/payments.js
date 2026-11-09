(function () {
  const gate = document.getElementById('subscription-gate');
  if (!gate) return;

  const form = document.getElementById('subscription-form');
  const email = document.getElementById('subscription-email');
  const createButton = document.getElementById('subscription-create');
  const statusEl = document.getElementById('subscription-status');
  const pixPanel = document.getElementById('pix-payment');
  const qrImage = document.getElementById('pix-qr');
  const pixCode = document.getElementById('pix-code');
  const copyButton = document.getElementById('pix-copy');
  const ticketLink = document.getElementById('pix-ticket');
  let currentPaymentId = null;
  let polling = false;

  function lock(message) {
    document.body.classList.add('subscription-locked');
    gate.hidden = false;
    if (message) statusEl.textContent = message;
  }

  function unlock(expiry) {
    document.body.classList.remove('subscription-locked');
    gate.hidden = true;
    if (expiry) console.info('ADA-M access active until', expiry);
  }

  async function checkAccess() {
    try {
      const response = await fetch('/api/payments/access', { credentials: 'same-origin', cache: 'no-store' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Não foi possível validar o acesso.');
      if (!data.payments_enabled || data.active) {
        unlock(data.expires_at);
      } else {
        lock('Seu acesso não está ativo. Gere um Pix para liberar o chat por 24 horas.');
      }
    } catch (error) {
      lock(error.message || 'Não foi possível validar o acesso. Atualize a página em instantes.');
    }
  }

  async function pollPayment(paymentId) {
    if (polling) return;
    polling = true;
    const started = Date.now();
    try {
      while (Date.now() - started < 15 * 60 * 1000) {
        await new Promise(resolve => setTimeout(resolve, 4000));
        const response = await fetch('/api/payments/status/' + encodeURIComponent(paymentId), {
          credentials: 'same-origin',
          cache: 'no-store'
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Falha ao consultar o pagamento.');
        if (data.active) {
          statusEl.textContent = 'Pagamento confirmado! Seu acesso de 24 horas foi liberado.';
          unlock(data.expires_at);
          return;
        }
        if (data.status === 'rejected' || data.status === 'cancelled' || data.status === 'refunded' || data.status === 'charged_back') {
          statusEl.textContent = 'Este pagamento não foi aprovado. Gere um novo Pix para tentar novamente.';
          return;
        }
        statusEl.textContent = 'Aguardando confirmação do Pix…';
      }
      statusEl.textContent = 'Ainda aguardando confirmação. Você pode manter esta página aberta; a verificação continuará ao atualizar.';
    } catch (error) {
      statusEl.textContent = error.message || 'Não foi possível verificar o pagamento.';
    } finally {
      polling = false;
    }
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const payerEmail = email.value.trim();
    if (!payerEmail || !email.checkValidity()) {
      email.reportValidity();
      return;
    }
    createButton.disabled = true;
    createButton.textContent = 'Gerando Pix…';
    statusEl.textContent = 'Conectando ao Mercado Pago…';
    try {
      const response = await fetch('/api/payments/pix', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: payerEmail })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Não foi possível gerar o Pix.');
      currentPaymentId = data.payment_id;
      pixCode.value = data.qr_code || '';
      if (data.qr_code_base64) {
        qrImage.src = 'data:image/png;base64,' + data.qr_code_base64;
        qrImage.hidden = false;
      } else {
        qrImage.hidden = true;
      }
      if (data.ticket_url) {
        ticketLink.href = data.ticket_url;
        ticketLink.hidden = false;
      } else {
        ticketLink.hidden = true;
      }
      pixPanel.hidden = false;
      statusEl.textContent = 'Pix gerado. Assim que o Mercado Pago confirmar, o acesso será liberado automaticamente.';
      pollPayment(currentPaymentId);
    } catch (error) {
      statusEl.textContent = error.message || 'Erro ao gerar Pix.';
    } finally {
      createButton.disabled = false;
      createButton.textContent = 'Gerar Pix de R$ 5,00';
    }
  });

  copyButton.addEventListener('click', async () => {
    if (!pixCode.value) return;
    try {
      await navigator.clipboard.writeText(pixCode.value);
      copyButton.textContent = 'Código Pix copiado!';
      setTimeout(() => { copyButton.textContent = 'Copiar código Pix'; }, 2200);
    } catch {
      pixCode.focus();
      pixCode.select();
      statusEl.textContent = 'Selecione e copie o código Pix manualmente.';
    }
  });

  checkAccess();
})();