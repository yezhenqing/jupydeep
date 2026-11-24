import { useEffect, useRef, useState } from 'react';
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList
} from '../ui/combobox';

import type { IConversationOption } from '../../datasync';

interface IConversation {
  id: string;
  title: string;
}

interface IConversationComboboxProps {
  options: IConversationOption[];
  selected: IConversationOption | null;
  onSelect: (id: string) => void;
  disabled?: boolean;
}

const NEW_CONVERSATION: IConversation = {
  id: '__new__',
  title: '+ New Conversation -- JupyDeep AI Partner'
};

function detectIsDarkTheme(): boolean {
  if (typeof document === 'undefined') {
    return false;
  }

  const body = document.body;
  if (body.classList.contains('jp-mod-dark')) {
    return true;
  }
  if (body.classList.contains('jp-mod-light')) {
    return false;
  }

  const themeLightAttr = body.getAttribute('data-jp-theme-light');
  if (themeLightAttr === 'false') {
    return true;
  }
  if (themeLightAttr === 'true') {
    return false;
  }

  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}

export default function ConversationCombobox({
  options,
  selected,
  onSelect,
  disabled = false
}: IConversationComboboxProps) {
  const [inputValue, setInputValue] = useState<string>(NEW_CONVERSATION.title);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [isDarkTheme, setIsDarkTheme] = useState<boolean>(detectIsDarkTheme);
  const anchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setInputValue(selected?.title ?? '');
    setIsSearching(false);
  }, [selected?.id, selected?.title]);

  // 进入流式状态时，若下拉菜单正开着则自动收起
  useEffect(() => {
    if (disabled && isOpen) {
      setIsOpen(false);
    }
  }, [disabled, isOpen]);

  useEffect(() => {
    const updateTheme = () => {
      setIsDarkTheme(detectIsDarkTheme());
    };

    updateTheme();

    const observer = new MutationObserver(updateTheme);
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class', 'data-jp-theme-light']
    });

    const mediaQuery = window.matchMedia?.('(prefers-color-scheme: dark)');
    mediaQuery?.addEventListener?.('change', updateTheme);

    return () => {
      observer.disconnect();
      mediaQuery?.removeEventListener?.('change', updateTheme);
    };
  }, []);

  const dropdownBg = isDarkTheme
    ? 'color-mix(in srgb, var(--jp-layout-color1) 88%, #ffffff 12%)'
    : 'color-mix(in srgb, var(--jp-layout-color1) 86%, #000000 14%)';

  const highlightBg = isDarkTheme
    ? 'rgba(255, 255, 255, 0.14)'
    : 'rgba(0, 0, 0, 0.10)';

  const selectedBg = isDarkTheme
    ? 'rgba(255, 255, 255, 0.06)'
    : 'rgba(0, 0, 0, 0.05)';

  return (
    <Combobox
      items={options}
      value={selected}
      open={isOpen}
      inputValue={inputValue}
      onOpenChange={nextOpen => {
        if (disabled && nextOpen) {
          return;
        }
        setIsOpen(nextOpen);
        if (nextOpen) {
          setIsSearching(false);
        }
      }}
      onInputValueChange={(val, details) => {
        setInputValue(val);
        if (
          details?.reason === 'input-change' ||
          details?.reason === 'input-clear' ||
          details?.reason === 'clear-press'
        ) {
          setIsSearching(true);
        }
      }}
      onValueChange={value => {
        if (disabled) {
          return;
        }
        const next = value as IConversationOption | null;
        if (next) {
          onSelect(next.id);
        }
      }}
      itemToStringValue={conv => (typeof conv === 'string' ? conv : conv.title)}
      filter={(itemValue, query) => {
        if (!isSearching) {
          return true;
        }
        const q = query.trim().toLowerCase();
        if (!q) {
          return true;
        }
        const title =
          typeof itemValue === 'string' ? itemValue : itemValue.title;
        return title.toLowerCase().includes(q);
      }}
    >
      <div ref={anchorRef} className="flex items-center w-full min-w-0">
        <ComboboxInput
          placeholder="Search or new conversation..."
          onFocus={() => setIsSearching(false)}
          className="h-6 text-xs border-[var(--jp-border-color1)] bg-transparent
                     text-[var(--jp-ui-font-color1)] w-full flex-1 min-w-0 truncate"
        />
      </div>

      <ComboboxContent
        anchor={anchorRef}
        align="start"
        sideOffset={6}
        style={{
          backgroundColor: dropdownBg,
          borderColor: 'var(--jp-border-color2)',
          color: 'var(--jp-ui-font-color1)'
        }}
        className="min-w-[16rem] w-max max-w-[26rem] border shadow-lg"
      >
        <ComboboxEmpty className="text-xs px-3 py-2 text-[var(--jp-ui-font-color3)]">
          No conversation found.
        </ComboboxEmpty>
        <ComboboxList>
          {(conv: IConversationOption) => (
            <ComboboxItem
              key={conv.id}
              value={conv}
              style={{
                color: 'var(--jp-ui-font-color1)',
                ['--item-highlight-bg' as string]: highlightBg,
                ['--item-selected-bg' as string]: selectedBg
              }}
              className="text-xs whitespace-nowrap pr-6 cursor-pointer rounded-sm
                         data-[selected]:[background-color:var(--item-selected-bg)]
                         data-[highlighted]:![background-color:var(--item-highlight-bg)]"
            >
              <span className="truncate">{conv.title}</span>
            </ComboboxItem>
          )}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
