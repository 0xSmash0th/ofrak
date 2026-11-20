<style>
  .container {
    min-height: 100%;
    display: flex;
    flex-direction: column;
    flex-wrap: nowrap;
    justify-content: center;
    align-items: stretch;
    align-content: center;
  }

  .inputs {
    flex-grow: 1;
  }

  .inputs *:first-child {
    margin-top: 0;
  }

  .row {
    margin-top: 1em;
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .actions {
    margin-top: 2em;
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    justify-content: space-evenly;
    align-items: center;
    align-content: center;
  }

  .error {
    margin-top: 2em;
    white-space: pre-wrap;
  }

  select,
  input {
    background-color: var(--main-bg-color);
    color: inherit;
    border: 1px solid;
    border-color: inherit;
    border-radius: 0;
    padding: 0.5em 1em;
    margin-left: 0.5em;
    font-size: inherit;
    font-family: var(--font);
    box-shadow: none;
  }
</style>

<script>
  import {
    selected,
    selectedResource,
    resourceNodeDataMap,
  } from "../stores.js";
  import Button from "../utils/Button.svelte";

  // These must match the Python view classes (pinned by test_set_memory_region_view_dotted_paths
  // in ofrak_core/tests/unit/test_error_and_tool_hints.py).
  const CODE_REGION = "ofrak.core.code_region.CodeRegion";
  const MEMORY_REGION = "ofrak.core.memory_region.MemoryRegion";

  export let modifierView;
  let errorMessage;
  let viewType = CODE_REGION;
  let virtualAddressInput = "0x0";
  let sizeInput = "";

  async function refreshResource() {
    // Force tree view children refresh (guard the map entry like the toolbar handlers do).
    if (!$resourceNodeDataMap[$selected]) {
      $resourceNodeDataMap[$selected] = {};
    }
    $resourceNodeDataMap[$selected].collapsed = false;
    $resourceNodeDataMap[$selected].childrenPromise =
      $selectedResource.get_children();

    // Force resource refresh by getting latest model from backend
    await $selectedResource.get_latest_model();

    // Force hex view refresh with colors
    const originalSelected = $selected;
    $selected = undefined;
    $selected = originalSelected;
  }

  function parseNonNegativeInt(raw, label) {
    // Number("") and Number("   ") are both 0, so reject empty/whitespace explicitly before
    // parsing, otherwise a blank field would silently submit 0. Number() accepts "0x90000" (hex)
    // and "589824" (decimal).
    if (raw === undefined || raw === null || String(raw).trim() === "") {
      throw Error(`${label} is required (use 0x... for hex, e.g. 0x90000).`);
    }
    const value = Number(raw);
    if (!Number.isInteger(value) || value < 0) {
      throw Error(
        `${label} "${raw}" is not a non-negative integer (use 0x... for hex).`
      );
    }
    return value;
  }

  async function setMemoryRegion() {
    errorMessage = undefined;
    let virtual_address, size;
    try {
      virtual_address = parseNonNegativeInt(
        virtualAddressInput,
        "virtual_address"
      );
      size = parseNonNegativeInt(sizeInput, "size");
      if (size === 0) {
        throw Error("size must be greater than 0.");
      }
    } catch (err) {
      errorMessage = err.message;
      return;
    }
    try {
      await $selectedResource.add_view(viewType, { virtual_address, size });
      await refreshResource();
      // Only close the dialog once the region is actually set; otherwise a backend error below
      // would be written to an unmounted component and the user would see nothing.
      modifierView = undefined;
    } catch (err) {
      try {
        const parsed = JSON.parse(err.message);
        errorMessage =
          parsed.message + (parsed.details ? `\n\n${parsed.details}` : "");
      } catch (_) {
        errorMessage = err.message;
      }
    }
  }
</script>

<div class="container">
  <div class="inputs">
    <p>
      Give this resource a memory region so Ghidra can map it. A
      <strong>CodeRegion</strong> is the executable ("rx") disassembly target
      for raw firmware; a plain <strong>MemoryRegion</strong> is non-executable ("rw").
      Set virtual_address and size (hex, e.g. 0x90000), then run Unpack/Analyze.
    </p>
    <div class="row">
      <span>Type</span>
      <select bind:value="{viewType}">
        <option value="{CODE_REGION}">CodeRegion (executable)</option>
        <option value="{MEMORY_REGION}">MemoryRegion</option>
      </select>
    </div>
    <div class="row">
      <span>virtual_address</span>
      <input bind:value="{virtualAddressInput}" placeholder="0x90000" />
    </div>
    <div class="row">
      <span>size</span>
      <input bind:value="{sizeInput}" placeholder="0x67c00" />
    </div>
  </div>
  {#if errorMessage}
    <p class="error">{errorMessage}</p>
  {/if}
  <div class="actions">
    <Button on:click="{setMemoryRegion}">Set Memory Region</Button>
    <Button on:click="{() => (modifierView = undefined)}">Cancel</Button>
  </div>
</div>
