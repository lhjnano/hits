<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../lib/api';
  import { categoriesStore } from '../lib/stores';
  import { t, subscribeLocale, getLocale } from '../lib/i18n';

  let categories = $state<{ name: string; icon: string; items: any[] }[]>([]);
  let expandedCategories = $state<Set<string>>(new Set());
  let loading = $state(true);
  let showNodeModal = $state(false);
  let showCategoryModal = $state(false);
  let editingCategory: string | null = $state(null);
  let editingNodeIndex: number | null = $state(null);

  // Form state
  let formCategoryName = $state('');
  let formCategoryIcon = $state('📁');
  let formNodeName = $state('');
  let formNodeLayer = $state('what');
  let formNodeType = $state('url');
  let formNodeAction = $state('');
  let formNodeNegative = $state(false);
  let formError = $state('');
  let formSubmitting = $state(false);

  // Reactive layer labels — re-evaluates when locale changes
  let localeTick = $state(0);
  let LAYER_LABELS = $derived<{
    why: string;
    how: string;
    what: string;
  }>({
    why: (localeTick, t('knowledge.layerWhy')),
    how: (localeTick, t('knowledge.layerHow')),
    what: (localeTick, t('knowledge.layerWhat')),
  });

  onMount(() => {
    const unsub = subscribeLocale(() => localeTick++);
    loadCategories();
    return unsub;
  });

  async function loadCategories() {
    loading = true;
    const res = await api.knowledge.list();
    if (res.success && res.data) {
      categories = res.data;
      categoriesStore.value = res.data;
      // Expand all by default
      expandedCategories = new Set(categories.map(c => c.name));
    }
    loading = false;
  }

  function toggleCategory(name: string) {
    const next = new Set(expandedCategories);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    expandedCategories = next;
  }

  function openAddCategory() {
    formCategoryName = '';
    formCategoryIcon = '📁';
    formError = '';
    showCategoryModal = true;
  }

  function openEditCategory(cat: { name: string; icon: string }) {
    editingCategory = cat.name;
    formCategoryName = cat.name;
    formCategoryIcon = cat.icon;
    formError = '';
    showCategoryModal = true;
  }

  function openAddNode(categoryName: string) {
    editingCategory = categoryName;
    editingNodeIndex = null;
    formNodeName = '';
    formNodeLayer = 'what';
    formNodeType = 'url';
    formNodeAction = '';
    formNodeNegative = false;
    formError = '';
    showNodeModal = true;
  }

  function openEditNode(categoryName: string, index: number, node: any) {
    editingCategory = categoryName;
    editingNodeIndex = index;
    formNodeName = node.name;
    formNodeLayer = node.layer;
    formNodeType = node.type;
    formNodeAction = node.action;
    formNodeNegative = node.negative_path || false;
    formError = '';
    showNodeModal = true;
  }

  async function saveCategory() {
    formError = '';
    formSubmitting = true;

    let res;
    if (editingCategory) {
      res = await api.knowledge.updateCategory(editingCategory, formCategoryName, formCategoryIcon);
    } else {
      res = await api.knowledge.createCategory(formCategoryName, formCategoryIcon);
    }

    formSubmitting = false;
    if (res.success) {
      showCategoryModal = false;
      editingCategory = null;
      await loadCategories();
    } else {
      formError = res.error || t('timeline.saveFailed');
    }
  }

  async function saveNode() {
    formError = '';
    if (!editingCategory) return;
    formSubmitting = true;

    let res;
    if (editingNodeIndex !== null) {
      res = await api.knowledge.updateNode(editingCategory, editingNodeIndex, {
        name: formNodeName,
        layer: formNodeLayer,
        type: formNodeType,
        action: formNodeAction,
        negative_path: formNodeNegative,
      });
    } else {
      res = await api.knowledge.addNode(editingCategory, {
        name: formNodeName,
        layer: formNodeLayer,
        type: formNodeType,
        action: formNodeAction,
        negative_path: formNodeNegative,
      });
    }

    formSubmitting = false;
    if (res.success) {
      showNodeModal = false;
      editingCategory = null;
      editingNodeIndex = null;
      await loadCategories();
    } else {
      formError = res.error || t('timeline.saveFailed');
    }
  }

  async function deleteCategory(name: string) {
    if (!confirm(t('knowledge.confirmDeleteCategory'))) return;
    await api.knowledge.deleteCategory(name);
    await loadCategories();
  }

  async function deleteNode(category: string, index: number) {
    if (!confirm(t('knowledge.confirmDeleteNode'))) return;
    await api.knowledge.deleteNode(category, index);
    await loadCategories();
  }
</script>

<div>
  <div class="flex items-center" style="margin-bottom:16px;">
    <h2 style="font-size:16px; flex:1;">📋 {t('knowledge.title')}</h2>
    <button class="btn btn-primary btn-sm" onclick={openAddCategory}>
      + {t('knowledge.addCategory')}
    </button>
  </div>

  {#if loading}
    <div class="loading"><div class="spinner"></div></div>
  {:else if categories.length === 0}
    <div class="empty-state">
      <div class="icon">📋</div>
      <div class="message">{t('knowledge.noCategories')}</div>
      <button class="btn btn-primary btn-sm" onclick={openAddCategory}>{t('knowledge.createCategory')}</button>
    </div>
  {:else}
    {#each categories as cat}
      <div style="margin-bottom:8px;">
        <div class="category-header" onclick={() => toggleCategory(cat.name)} role="button" tabindex="0">
          <span class="icon">{cat.icon}</span>
          <span class="name">{cat.name}</span>
          <span class="count">{cat.items?.length || 0}</span>
          <div class="actions">
            <button
              class="btn-icon"
              style="width:24px;height:24px;font-size:12px;"
              onclick={(e) => { e.stopPropagation(); openAddNode(cat.name); }}
              title={t('knowledge.newNode')}
            >+</button>
            <button
              class="btn-icon"
              style="width:24px;height:24px;font-size:10px;"
              onclick={(e) => { e.stopPropagation(); openEditCategory(cat); }}
              title={t('knowledge.editCategory')}
            >✏</button>
            <button
              class="btn-icon"
              style="width:24px;height:24px;font-size:10px;color:var(--danger);"
              onclick={(e) => { e.stopPropagation(); deleteCategory(cat.name); }}
              title={t('delete')}
            >✕</button>
          </div>
          <span style="font-size:10px;color:var(--text-muted);">
            {expandedCategories.has(cat.name) ? '▼' : '▶'}
          </span>
        </div>

        {#if expandedCategories.has(cat.name) && cat.items}
          {#each cat.items as node, i}
            <div
              class="node-item layer-{node.layer}"
              class:negative-path={node.negative_path}
            >
              <span class="badge badge-{node.layer}">{node.layer.toUpperCase()}</span>
              <span class="node-name">{node.name}</span>
              <span class="node-action">{node.action}</span>
              <button
                class="btn-icon"
                style="width:20px;height:20px;font-size:10px;opacity:0.5;"
                onclick={() => openEditNode(cat.name, i, node)}
                title={t('edit')}
              >✏</button>
              <button
                class="btn-icon"
                style="width:20px;height:20px;font-size:10px;opacity:0.5;color:var(--danger);"
                onclick={() => deleteNode(cat.name, i)}
                title={t('delete')}
              >✕</button>
            </div>
          {/each}
        {/if}
      </div>
    {/each}
  {/if}
</div>

<!-- Category Modal -->
{#if showCategoryModal}
  <div class="modal-overlay" onclick={() => showCategoryModal = false}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>{editingCategory ? t('knowledge.editCategory') : t('knowledge.createCategory')}</h2>
      <div class="form-group">
        <label>{t('knowledge.categoryName')}</label>
        <input class="input" bind:value={formCategoryName} placeholder={t('knowledge.categoryName')} />
      </div>
      <div class="form-group">
        <label>{t('knowledge.categoryIcon')}</label>
        <input class="input" bind:value={formCategoryIcon} placeholder="📁" style="width:80px;" />
      </div>
      {#if formError}
        <div class="error-msg">{formError}</div>
      {/if}
      <div class="flex gap-sm" style="margin-top:16px; justify-content:flex-end;">
        <button class="btn btn-secondary" onclick={() => showCategoryModal = false}>{t('cancel')}</button>
        <button class="btn btn-primary" onclick={saveCategory} disabled={formSubmitting}>
          {formSubmitting ? t('knowledge.saving') : t('save')}
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- Node Modal -->
{#if showNodeModal}
  <div class="modal-overlay" onclick={() => showNodeModal = false}>
    <div class="modal" onclick={(e) => e.stopPropagation()}>
      <h2>{editingNodeIndex !== null ? t('knowledge.editNode') : t('knowledge.newNode')}</h2>
      <div class="form-group">
        <label>{t('knowledge.nodeName')}</label>
        <input class="input" bind:value={formNodeName} placeholder={t('knowledge.nodeName')} />
      </div>
      <div class="form-group">
        <label>{t('knowledge.nodeLayer')}</label>
        <select class="input" bind:value={formNodeLayer}>
          <option value="why">{t('knowledge.layerWhy')}</option>
          <option value="how">{t('knowledge.layerHow')}</option>
          <option value="what">{t('knowledge.layerWhat')}</option>
        </select>
      </div>
      <div class="form-group">
        <label>{t('knowledge.nodeType')}</label>
        <select class="input" bind:value={formNodeType}>
          <option value="url">{t('knowledge.typeUrl')}</option>
          <option value="shell">{t('knowledge.typeShell')}</option>
        </select>
      </div>
      <div class="form-group">
        <label>{t('knowledge.nodeAction')}</label>
        <input class="input" bind:value={formNodeAction} placeholder="https://... " />
      </div>
      <div class="form-group">
        <label style="display:flex;align-items:center;gap:8px;">
          <input type="checkbox" bind:checked={formNodeNegative} />
          {t('knowledge.negativePath')}
        </label>
      </div>
      {#if formError}
        <div class="error-msg">{formError}</div>
      {/if}
      <div class="flex gap-sm" style="margin-top:16px; justify-content:flex-end;">
        <button class="btn btn-secondary" onclick={() => showNodeModal = false}>{t('cancel')}</button>
        <button class="btn btn-primary" onclick={saveNode} disabled={formSubmitting}>
          {formSubmitting ? t('knowledge.saving') : t('save')}
        </button>
      </div>
    </div>
  </div>
{/if}
