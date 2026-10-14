// Exercise Pi's installed SDK loader/read tool without an Agent/model session.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const [sdkPath, cwd, agentDir, resourcesJson, optionsJson] = process.argv.slice(2);
const { AgentSession, DefaultResourceLoader, SettingsManager, createReadToolDefinition, formatSkillsForPrompt } =
  await import(pathToFileURL(sdkPath).href);
const options = JSON.parse(optionsJson);
const settingsManager = SettingsManager.create(cwd, agentDir, { projectTrusted: options.trusted });
settingsManager.setProjectTrusted(options.trusted);
const loader = new DefaultResourceLoader({
  cwd, agentDir, settingsManager,
  noExtensions: true, noPromptTemplates: true, noThemes: true, noSkills: options.disabled,
});
await loader.reload();
const loaded = loader.getSkills();
const names = new Set(["github-collaboration-setup", "github-collaboration", "github-collaboration-check"]);
const resources = JSON.parse(resourcesJson);
const skills = loaded.skills.filter(skill => names.has(skill.name) && resources.includes(skill.filePath));
const expansions = skills.map(skill => {
  // Installed runtime method; this proves local expansion, not LLM compliance.
  const expanded = AgentSession.prototype._expandSkillCommand.call(
    { resourceLoader: loader }, `/skill:${skill.name} disposable-test-argument`,
  );
  const original = readFileSync(skill.filePath, "utf8");
  const body = original.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "").trim();
  return {
    name: skill.name, actual_path: skill.filePath,
    contains_full_body: expanded.includes(body), contains_base_dir: expanded.includes(skill.baseDir),
    arguments_preserved: expanded.endsWith("disposable-test-argument"),
    expanded_sha256: createHash("sha256").update(expanded).digest("hex"),
  };
});
const readTool = createReadToolDefinition(cwd);
const reads = [];
for (const path of resources) {
  const read = await readTool.execute("discovery-read", { path });
  reads.push({ path, ok: read.content.some(part => part.type === "text" && part.text.length > 0),
               truncated: Boolean(read.details?.truncation?.truncated) });
}
console.log(JSON.stringify({
  interface: "installed SDK DefaultResourceLoader.reload/getSkills + AgentSession skill expansion + read tool",
  skills, diagnostics: loaded.diagnostics.filter(item => [...names].some(name => JSON.stringify(item).includes(name))), expansions,
  outside_fixture_same_name_count: loaded.skills.filter(skill => names.has(skill.name) && !resources.includes(skill.filePath)).length,
  prompt_metadata_contains_all: skills.length === names.size && skills.every(skill => formatSkillsForPrompt(skills).includes(skill.filePath)),
  context_files: loader.getAgentsFiles().agentsFiles.filter(file => file.content.includes("platform-entry:")).map(file => ({ path: file.path, contains_test_entry: true })),
  project_trusted: options.trusted, discovery_disabled: options.disabled,
  resource_reads: { attempted: reads.length, successful: reads.filter(read => read.ok).length,
                    truncated: reads.filter(read => read.truncated).length, failures: reads.filter(read => !read.ok) },
  model_turns_sent: 0,
}));
