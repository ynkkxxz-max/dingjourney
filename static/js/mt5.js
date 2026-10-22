/**
 * Journa NextGen - MetaTrader 5 Sync, Report Import, and REAL/DEMO Management
 * 100% Safe: No password required!
 */

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    setupMT5Handlers();
  });
} else {
  setupMT5Handlers();
}

function setupMT5Handlers() {
  // Start automatic real-time sync in background
  startMT5AutoSync();

  const btnMt5Modal = document.getElementById('btnMt5Modal');
  const closeMt5Modal = document.getElementById('closeMt5Modal');

  if (btnMt5Modal) {
    btnMt5Modal.addEventListener('click', () => {
      openModal('mt5Modal');
      refreshMT5ModalStatus();
    });
  }

  if (closeMt5Modal) {
    closeMt5Modal.addEventListener('click', () => {
      closeModal('mt5Modal');
    });
  }

  // MT5 Modal Tabs
  const tabDirect = document.getElementById('tabMt5Direct');
  const tabImport = document.getElementById('tabMt5Import');
  const tabEa = document.getElementById('tabMt5Ea');
  const tabIos = document.getElementById('tabMt5Ios');

  const contentDirect = document.getElementById('mt5ContentDirect');
  const contentImport = document.getElementById('mt5ContentImport');
  const contentEa = document.getElementById('mt5ContentEa');
  const contentIos = document.getElementById('mt5ContentIos');

  const tabs = [
    { btn: tabDirect, content: contentDirect },
    { btn: tabEa, content: contentEa },
    { btn: tabImport, content: contentImport },
    { btn: tabIos, content: contentIos }
  ];

  tabs.forEach(t => {
    if (t.btn && t.content) {
      t.btn.addEventListener('click', () => {
        tabs.forEach(item => {
          if (item.btn) item.btn.classList.remove('active');
          if (item.content) item.content.style.display = 'none';
        });
        t.btn.classList.add('active');
        t.content.style.display = 'block';
      });
    }
  });

  // Collapsible Import Section Toggle
  const toggleImportBtn = document.getElementById('toggleImportSectionBtn');
  const collapsibleImport = document.getElementById('collapsibleImportArea');
  if (toggleImportBtn && collapsibleImport) {
    toggleImportBtn.addEventListener('click', (e) => {
      e.preventDefault();
      const isHidden = collapsibleImport.style.display === 'none' || collapsibleImport.style.display === '';
      collapsibleImport.style.display = isHidden ? 'block' : 'none';
      toggleImportBtn.textContent = isHidden ? '▲ បិទផ្ទាំង Import Report' : '📂 ចង់ Import File Report (HTML/CSV)? ចុចទីនេះ';
    });
  }

  // Load and populate Security PIN & Target Account
  async function loadSecuritySettings() {
    try {
      const res = await fetch('/api/config');
      const cfg = await res.json();
      const targetAccInput = document.getElementById('targetAccountInput');
      const syncPinInput = document.getElementById('syncPinInput');
      const eaSyncPinDisplay = document.getElementById('eaSyncPinDisplay');

      if (targetAccInput && cfg.target_account !== undefined) {
        targetAccInput.value = cfg.target_account;
      }
      if (syncPinInput && cfg.sync_pin) {
        syncPinInput.value = cfg.sync_pin;
      }
      if (eaSyncPinDisplay && cfg.sync_pin) {
        eaSyncPinDisplay.value = cfg.sync_pin;
      }
    } catch (e) {
      console.error('Failed to load security settings:', e);
    }
  }
  loadSecuritySettings();

  // Save Security Settings Button
  const btnSaveSecurity = document.getElementById('btnSaveSecurity');
  if (btnSaveSecurity) {
    btnSaveSecurity.addEventListener('click', async () => {
      const targetAccInput = document.getElementById('targetAccountInput');
      const syncPinInput = document.getElementById('syncPinInput');
      const eaSyncPinDisplay = document.getElementById('eaSyncPinDisplay');

      const target_account = targetAccInput ? targetAccInput.value.trim() : '';
      const sync_pin = syncPinInput ? syncPinInput.value.trim() : 'JN-8899';

      if (!sync_pin) {
        showToast('Please enter a valid Sync PIN!', 'error');
        return;
      }

      try {
        btnSaveSecurity.disabled = true;
        btnSaveSecurity.textContent = '...';
        const res = await fetch('/api/config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_account, sync_pin })
        });
        const result = await res.json();
        if (result.success) {
          if (eaSyncPinDisplay) eaSyncPinDisplay.value = sync_pin;
          showToast('MT5 Account ID & Sync PIN saved successfully!', 'success');
        } else {
          showToast('Failed to save security settings.', 'error');
        }
      } catch (err) {
        console.error(err);
        showToast('Error saving security settings.', 'error');
      } finally {
        btnSaveSecurity.disabled = false;
        btnSaveSecurity.textContent = 'Save';
      }
    });
  }

  // Copy PIN Button
  const btnCopyPin = document.getElementById('btnCopyPin');
  if (btnCopyPin) {
    btnCopyPin.addEventListener('click', () => {
      const eaSyncPinDisplay = document.getElementById('eaSyncPinDisplay') || document.getElementById('syncPinInput');
      if (eaSyncPinDisplay) {
        navigator.clipboard.writeText(eaSyncPinDisplay.value).then(() => {
          showToast('Sync PIN copied to clipboard!', 'success');
        }).catch(() => {
          showToast('PIN: ' + eaSyncPinDisplay.value, 'info');
        });
      }
    });
  }

  // Dynamic Webhook URL input & copy
  const webhookInput = document.getElementById('webhookUrlInput');
  const btnCopyWebhook = document.getElementById('btnCopyWebhook');
  if (webhookInput) {
    webhookInput.value = `${window.location.origin}/api/mt5/webhook`;
  }
  if (btnCopyWebhook && webhookInput) {
    btnCopyWebhook.addEventListener('click', () => {
      navigator.clipboard.writeText(webhookInput.value).then(() => {
        showToast('Webhook URL copied to clipboard!', 'success');
      }).catch(() => {
        webhookInput.select();
        document.execCommand('copy');
        showToast('Webhook URL copied!', 'success');
      });
    });
  }

  // REAL vs DEMO Account Type Switcher
  const btnReal = document.getElementById('btnModeReal');
  const btnDemo = document.getElementById('btnModeDemo');

  if (btnReal && btnDemo) {
    btnReal.addEventListener('click', async () => {
      btnReal.classList.add('buy-active');
      btnDemo.classList.remove('sell-active');
      await updateAccountType('REAL');
    });

    btnDemo.addEventListener('click', async () => {
      btnDemo.classList.add('sell-active');
      btnReal.classList.remove('buy-active');
      await updateAccountType('DEMO');
    });
  }

  // 1-Click MT5 Sync Button with PIN and Target Account Collision Prevention
  const btnTriggerSync = document.getElementById('btnTriggerMt5Sync');
  if (btnTriggerSync) {
    btnTriggerSync.addEventListener('click', async () => {
      const targetAccInput = document.getElementById('targetAccountInput');
      const syncPinInput = document.getElementById('syncPinInput');
      const target_account = targetAccInput ? targetAccInput.value.trim() : '';
      const sync_pin = syncPinInput ? syncPinInput.value.trim() : '';

      btnTriggerSync.disabled = true;
      btnTriggerSync.textContent = 'Connecting to MT5 Terminal...';
      showToast('Connecting to MT5...', 'info');

      try {
        const res = await fetch('/api/mt5/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            days_back: 180,
            target_account: target_account || null,
            sync_pin: sync_pin || null
          })
        });
        const result = await res.json();

        if (result.success) {
          const acc = result.account || {};
          const accType = acc.account_type || 'REAL';
          showToast(`Connected to MT5 (${accType} #${acc.login})! Synced ${result.synced_trades} trades.`, 'success');

          // Update starting capital from live account balance
          if (acc.balance) {
            await fetch('/api/config', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ 
                starting_capital: acc.balance,
                account_name: `${acc.broker || 'MT5'} (${acc.login})`,
                account_type: accType,
                target_account: String(acc.login)
              })
            });
            if (targetAccInput && !targetAccInput.value) {
              targetAccInput.value = acc.login;
            }
          }

          await refreshDashboard();
          await refreshMT5ModalStatus();
          await checkMT5LiveStatus();
        } else {
          showToast(result.error || 'Could not connect to MT5. Ensure MT5 is running on your PC.', 'error');
        }
      } catch (err) {
        console.error(err);
        showToast('Error communicating with MT5 service.', 'error');
      } finally {
        btnTriggerSync.disabled = false;
        btnTriggerSync.textContent = 'Connect Active MT5 Terminal';
      }
    });
  }

  // Account ID & Server Direct Login Form (No password required if saved in MT5)
  const investorForm = document.getElementById('mt5InvestorLoginForm');
  if (investorForm) {
    investorForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const login = document.getElementById('investorLoginInput').value.trim();
      const passElem = document.getElementById('investorPasswordInput');
      const password = passElem ? passElem.value : null;
      const server = document.getElementById('investorServerInput').value.trim();
      const submitBtn = investorForm.querySelector('button[type="submit"]');

      if (!login || !server) {
        showToast('Please fill in MT5 Login ID and Server Name.', 'error');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = 'Connecting...';
      showToast('Connecting to MT5...', 'info');

      try {
        const payload = { login: parseInt(login, 10), server };
        if (password) payload.password = password;

        const res = await fetch('/api/mt5/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await res.json();

        if (result.success) {
          const acc = result.account || {};
          const accType = acc.account_type || 'REAL';
          showToast(`Successfully connected to ${acc.broker || 'MT5'} (${accType})! Synced ${result.synced_trades || 0} trades.`, 'success');

          if (acc.balance) {
            await fetch('/api/config', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                starting_capital: acc.balance,
                account_name: `${acc.broker || 'MT5'} (${acc.login})`,
                account_type: accType
              })
            });
          }

          investorForm.reset();
          await refreshDashboard();
          await refreshMT5ModalStatus();
          await checkMT5LiveStatus();
        } else {
          showToast(result.error || 'Failed to login to MT5.', 'error');
        }
      } catch (err) {
        console.error(err);
        showToast('Error communicating with MT5 service.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Connect with Investor Password';
      }
    });
  }

  // Drag & Drop / File Upload Handler (Import Report HTML/CSV)
  const dropzone = document.getElementById('reportDropzone');
  const fileInput = document.getElementById('reportFileInput');

  if (dropzone && fileInput) {
    dropzone.addEventListener('click', () => fileInput.click());

    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
      dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', async (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files.length > 0) {
        await uploadStatementFile(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', async () => {
      if (fileInput.files.length > 0) {
        await uploadStatementFile(fileInput.files[0]);
      }
    });
  }
}

async function updateAccountType(type) {
  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ account_type: type })
    });
    showToast(`Account set to ${type}`, 'success');
    await refreshDashboard();
  } catch (err) {
    console.error(err);
  }
}

async function uploadStatementFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  showToast(`Uploading ${file.name}...`, 'info');

  try {
    const res = await fetch('/api/trades/import', {
      method: 'POST',
      body: formData
    });
    const result = await res.json();
    if (result.success) {
      showToast(`Imported ${result.imported_count} trades successfully!`, 'success');
      closeModal('mt5Modal');
      await refreshDashboard();
    } else {
      showToast(result.detail || 'Import failed', 'error');
    }
  } catch (err) {
    console.error(err);
    showToast('Failed to upload file', 'error');
  }
}

async function refreshMT5ModalStatus() {
  try {
    const res = await fetch('/api/mt5/status');
    const data = await res.json();

    const connectedCard = document.getElementById('mt5AccountConnectedCard');
    const storedAcc = data.stored_account;

    if (storedAcc && storedAcc.account_number) {
      connectedCard.style.display = 'block';
      document.getElementById('mt5CardAccount').textContent = storedAcc.account_number;
      document.getElementById('mt5CardBroker').textContent = storedAcc.broker || storedAcc.server || 'MT5';
      document.getElementById('mt5CardBalance').textContent = `$${Number(storedAcc.balance || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
      document.getElementById('mt5CardEquity').textContent = `$${Number(storedAcc.equity || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
      document.getElementById('mt5LastSyncTime').textContent = storedAcc.last_sync ? `Synced: ${storedAcc.last_sync}` : '';

      const badge = document.getElementById('mt5CardTypeBadge');
      const accType = storedAcc.account_type || 'REAL';
      if (badge) {
        badge.textContent = accType;
        badge.className = `account-badge ${accType.toLowerCase()}`;
      }

      // Sync radio button state
      const btnReal = document.getElementById('btnModeReal');
      const btnDemo = document.getElementById('btnModeDemo');
      if (btnReal && btnDemo) {
        if (accType === 'DEMO') {
          btnDemo.classList.add('sell-active');
          btnReal.classList.remove('buy-active');
        } else {
          btnReal.classList.add('buy-active');
          btnDemo.classList.remove('sell-active');
        }
      }
    } else {
      connectedCard.style.display = 'none';
    }
  } catch (err) {
    console.error(err);
  }
}

// Automatic Real-Time MT5 Background Poller (every 2 seconds for instant SL/TP change)
let autoSyncInterval = null;
let lastKnownBalance = null;

function startMT5AutoSync() {
  if (autoSyncInterval) return;
  autoSyncInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/mt5/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days_back: 3 })
      });
      if (res.ok) {
        const data = await res.json();
        if (data.success && data.account) {
          const currentBal = Number(data.account.balance);
          // If balance changed (e.g. SL or TP hit)
          if (lastKnownBalance !== null && currentBal !== lastKnownBalance) {
            const diff = currentBal - lastKnownBalance;
            const diffStr = diff >= 0 ? `+$${diff.toFixed(2)}` : `-$${Math.abs(diff).toFixed(2)}`;
            const noticeType = diff >= 0 ? 'TP Hit' : 'SL Hit';
            if (typeof showToast === 'function') {
              showToast(`⚡ ${noticeType} (${diffStr})! Calendar updated.`, diff >= 0 ? 'success' : 'error');
            }
            if (typeof refreshDashboard === 'function') {
              await refreshDashboard();
            }
            if (typeof checkMT5LiveStatus === 'function') {
              checkMT5LiveStatus();
            }
          }
          lastKnownBalance = currentBal;
        }
      }
    } catch (e) {
      // background polling - silent
    }
  }, 2000); // Poll every 2 seconds for instant SL/TP updates!
}
