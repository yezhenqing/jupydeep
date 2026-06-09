import React, { useState, useCallback } from 'react';
import { FieldProps } from '@rjsf/utils';
import { useEngineCatalog } from '../hooks/useEngine';

interface IAgentConfigData {
  enabled?: boolean;
  description?: string;
  model?: string;
  deep_mcps?: string[];
  capabilities?: string[];
  deep_skills?: string[];
}

interface IAgentsFormData {
  [agentName: string]: IAgentConfigData;
}

const EMPTY_ARRAY: any[] = [];

const AgentsField: React.FC<FieldProps> = props => {
  const { schema, formData = {}, onChange, disabled, readonly } = props;

  const { data: engineData, isLoading } = useEngineCatalog();
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  const rootSchema = (props as any).registry?.rootSchema || schema;
  const agentConfigDefinition = rootSchema.definitions?.AgentConfig as any;

  const schemaCapabs =
    agentConfigDefinition?.properties?.capabilities?.items?.enum;

  const capablitiesEnum: string[] = schemaCapabs || [
    'include_todo',
    'include_filesystem',
    'include_subagents',
    'include_plan',
    'include_liteparse',
    'context_manager',
    'web_search',
    'web_fetch',
    'cost_tracking',
    'include_checkpoints',
    'include_teams',
    'include_memory'
  ];

  const llmsEnum = engineData?.payload?.llms || EMPTY_ARRAY;
  const skillsEnum = engineData?.payload?.skills || EMPTY_ARRAY;
  const mcpsEnum = engineData?.payload?.mcps || EMPTY_ARRAY;

  const engineAgents = engineData?.payload?.agents || {};
  const agentKeys = Object.keys(engineAgents);

  const toggleAgent = useCallback((agentName: string) => {
    setExpandedAgents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(agentName)) {
        newSet.delete(agentName);
      } else {
        newSet.add(agentName);
      }
      return newSet;
    });
  }, []);

  const checkboxDisabled = disabled || readonly;
  const checkboxClass = checkboxDisabled
    ? 'cursor-not-allowed'
    : 'cursor-pointer';
  const labelClass = checkboxDisabled ? 'cursor-not-allowed' : 'cursor-pointer';

  if (isLoading || !engineData) {
    return (
      <div className="p-5 text-center text-[var(--jp-ui-font-color2)] font-sans">
        Loading agent configurations...
      </div>
    );
  }

  if (agentKeys.length === 0) {
    return (
      <div className="mb-5 font-sans">
        <div className="flex justify-between items-center mb-4 pb-2 border-b-2 border-[var(--jp-border-color2)]">
          <h3 className="text-lg font-semibold text-[var(--jp-ui-font-color1)] m-0">
            Available Agents
          </h3>
        </div>
        <div className="p-10 text-center bg-[var(--jp-layout-color2)] border border-dashed border-[var(--jp-border-color2)] rounded-lg text-[var(--jp-ui-font-color2)]">
          No agents available
        </div>
      </div>
    );
  }

  return (
    <div className="mb-5 font-sans">
      {/* Header Controls */}
      <div className="flex justify-between items-center mb-4 pb-2 border-b-2 border-[var(--jp-border-color2)]">
        <div>
          <h3 className="text-lg font-semibold text-[var(--jp-ui-font-color1)] m-0">
            Available Agents
          </h3>
          <div className="text-sm text-[var(--jp-ui-font-color2)] mt-1">
            {agentKeys.length} agent(s)
          </div>
        </div>
        <button
          type="button"
          className="px-3 py-1 text-xs bg-[var(--jp-layout-color2)] border border-[var(--jp-border-color2)] rounded text-[var(--jp-ui-font-color1)] cursor-pointer hover:bg-[var(--jp-layout-color3)]"
          onClick={() =>
            setExpandedAgents(
              expandedAgents.size === agentKeys.length
                ? new Set()
                : new Set(agentKeys)
            )
          }
        >
          {expandedAgents.size === agentKeys.length
            ? 'Collapse All'
            : 'Expand All'}
        </button>
      </div>

      {/* Agent list */}
      {agentKeys.map(agentName => {
        const formAgentData = (formData as IAgentsFormData)[agentName];
        const defaultAgentData = engineAgents[agentName] || {};

        const agentData: IAgentConfigData = {
          enabled: formAgentData?.enabled ?? defaultAgentData?.enabled ?? true,
          description:
            defaultAgentData?.description ?? formAgentData?.description ?? '',
          model:
            formAgentData?.model ??
            defaultAgentData?.model ??
            defaultAgentData?.LLM ??
            '',
          deep_mcps:
            formAgentData?.deep_mcps ??
            defaultAgentData?.deep_mcps ??
            defaultAgentData?.MCPs ??
            EMPTY_ARRAY,
          capabilities:
            formAgentData?.capabilities ??
            defaultAgentData?.capabilities ??
            defaultAgentData?.features ??
            EMPTY_ARRAY,
          deep_skills:
            formAgentData?.deep_skills ??
            defaultAgentData?.deep_skills ??
            defaultAgentData?.skills ??
            EMPTY_ARRAY
        };

        const isExpanded = expandedAgents.has(agentName);
        const isEnabled = agentData.enabled === true;
        const isLLMsEmpty = llmsEnum.length === 0;
        const isAgentDisabled = checkboxDisabled || isLLMsEmpty;

        return (
          <div
            key={agentName}
            className="mb-4 border border-[var(--jp-border-color2)] rounded-lg overflow-hidden bg-[var(--jp-layout-color1)]"
          >
            {/* Accordion Header */}
            <div
              className="flex justify-between items-center p-3 px-4 bg-[var(--jp-layout-color2)] cursor-pointer select-none"
              onClick={() => toggleAgent(agentName)}
            >
              <div className="flex items-center gap-3">
                <span
                  className="text-sm transition-transform duration-200"
                  style={{
                    transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'
                  }}
                >
                  ▶
                </span>
                <span className="text-base font-semibold text-[var(--jp-ui-font-color1)]">
                  {agentName}
                </span>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${
                    isLLMsEmpty
                      ? 'bg-[var(--jp-error-color1)] text-white'
                      : isEnabled
                        ? 'bg-[var(--jp-success-color1)] text-white'
                        : 'bg-[var(--jp-error-color1)] text-white'
                  }`}
                >
                  {isLLMsEmpty
                    ? 'Disabled (No LLM)'
                    : isEnabled
                      ? 'Enabled'
                      : 'Disabled'}
                </span>
              </div>
            </div>

            <div className={isExpanded ? 'p-4' : 'hidden'}>
              <div className="mb-4">
                <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
                  Enable Agent
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="checkbox"
                    className={checkboxClass}
                    checked={isLLMsEmpty ? false : agentData.enabled}
                    onChange={e => {
                      onChange({
                        ...(formData as IAgentsFormData),
                        [agentName]: { ...agentData, enabled: e.target.checked }
                      });
                    }}
                    disabled={isAgentDisabled}
                  />
                  <label
                    className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                  >
                    Enable this agent
                  </label>
                </div>
              </div>

              {/* (Description) */}
              <div className="mb-4">
                <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
                  Description
                </label>
                <textarea
                  className="w-full p-2 text-sm font-sans border border-[var(--jp-border-color2)]
                          rounded bg-[var(--jp-layout-color1)] text-[var(--jp-ui-font-color1)] resize-y min-h-[120px]"
                  defaultValue={agentData.description || ''}
                  onBlur={e => {
                    const newValue = e.target.value;
                    const oldValue = agentData.description || '';

                    if (newValue.trim() !== oldValue.trim()) {
                      onChange({
                        ...(formData as IAgentsFormData),
                        [agentName]: { ...agentData, description: newValue }
                      });
                    }
                  }}
                  placeholder="Enter agent description..."
                  disabled={disabled || readonly || isLLMsEmpty}
                />
              </div>

              {/* LLM Selection (agent_llm - single select) */}
              <div className="mb-4">
                <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
                  Language Model (LLM)
                </label>
                {isLLMsEmpty ? (
                  <div className="text-sm text-orange-500 italic">
                    Not available. Please configure at least one functioning
                    LLM.
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-x-4 gap-y-2 mt-2">
                    {llmsEnum.map((modelName: string) => (
                      <div
                        key={modelName}
                        className="flex items-center gap-1.5 py-0.5"
                      >
                        <input
                          type="radio"
                          name={`${agentName}-llm-selection`}
                          className={`${checkboxClass} rounded-full`}
                          checked={agentData.model === modelName}
                          onChange={e => {
                            if (e.target.checked) {
                              onChange({
                                ...(formData as IAgentsFormData),
                                [agentName]: { ...agentData, model: modelName }
                              });
                            }
                          }}
                          disabled={checkboxDisabled}
                        />
                        <label
                          className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                        >
                          {modelName}
                        </label>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* MCP Selection (agent_mcps - Multi) */}
              <div className="mb-4">
                <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
                  MCP Servers
                </label>
                <div className="flex flex-wrap gap-3 mt-2">
                  {mcpsEnum.map((mcpName: string) => (
                    <div key={mcpName} className="flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        className={checkboxClass}
                        checked={(agentData.deep_mcps || []).includes(mcpName)}
                        onChange={e => {
                          const current = agentData.deep_mcps || [];
                          const newMCPs = e.target.checked
                            ? [...current, mcpName]
                            : current.filter(f => f !== mcpName);
                          onChange({
                            ...(formData as IAgentsFormData),
                            [agentName]: { ...agentData, deep_mcps: newMCPs }
                          });
                        }}
                        disabled={isAgentDisabled}
                      />
                      <label
                        className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                      >
                        {mcpName}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Core Capabilities Selection (agent_capabilities - multi-select) */}
              <div className="mb-4">
                <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
                  Capabilities
                </label>
                <div className="flex flex-wrap gap-3 mt-2">
                  {capablitiesEnum.map(capab => (
                    <div key={capab} className="flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        className={checkboxClass}
                        checked={(agentData.capabilities || []).includes(capab)}
                        onChange={e => {
                          const current = agentData.capabilities || [];
                          const newCapabs = e.target.checked
                            ? [...current, capab]
                            : current.filter(f => f !== capab);
                          onChange({
                            ...(formData as IAgentsFormData),
                            [agentName]: {
                              ...agentData,
                              capabilities: newCapabs
                            }
                          });
                        }}
                        disabled={isAgentDisabled}
                      />
                      <label
                        className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                      >
                        {capab}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Skill Selection (agent_skills - multi-select) */}
              <div className="mb-4">
                <label className="text-sm font-bold text-[var(--jp-ui-font-color1)] mb-2 block">
                  Skills
                </label>
                <div className="flex flex-wrap gap-3 mt-2">
                  {skillsEnum.map((skill: string) => (
                    <div key={skill} className="flex items-center gap-1.5">
                      <input
                        type="checkbox"
                        className={checkboxClass}
                        checked={(agentData.deep_skills || []).includes(skill)}
                        onChange={e => {
                          const current = agentData.deep_skills || [];
                          const newSkills = e.target.checked
                            ? [...current, skill]
                            : current.filter(s => s !== skill);
                          onChange({
                            ...(formData as IAgentsFormData),
                            [agentName]: {
                              ...agentData,
                              deep_skills: newSkills
                            }
                          });
                        }}
                        disabled={isAgentDisabled}
                      />
                      <label
                        className={`text-sm text-[var(--jp-ui-font-color1)] ${labelClass}`}
                      >
                        {skill}
                      </label>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bottom Summary Statistics */}
              {((agentData.capabilities?.length || 0) > 0 ||
                (agentData.deep_skills?.length || 0) > 0) && (
                <div className="mt-3 pt-3 border-t border-[var(--jp-border-color2)] text-xs text-[var(--jp-ui-font-color2)]">
                  Summary: {agentData.capabilities?.length || 0} capability(ies)
                  · {agentData.deep_skills?.length || 0} skill(s)
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default AgentsField;
