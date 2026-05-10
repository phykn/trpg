import React from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  Keyboard,
  Platform,
  type NativeSyntheticEvent,
  type TextInputContentSizeChangeEventData,
  type TextInputSubmitEditingEventData,
} from 'react-native';

import { colors } from '@/design/tokens';
import { ko } from '@/locale/ko';
import { Surface } from '@/components/ui';
import type { PanelAction } from '@/logic/info-panel';
import type { NearbyPanelModel } from '@/logic/story-graph';

import { SendButton } from './SendButton';
import { StopButton } from './StopButton';

const INPUT_MIN_HEIGHT = 40;
const INPUT_MAX_HEIGHT = 320;
const IS_WEB = Platform.OS === 'web';

export function Composer({ input, setInput, onSend, onStop, streaming, locked = false, nearby = null, onNearbyAction }: {
  input: string;
  setInput: (text: string) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  locked?: boolean;
  nearby?: NearbyPanelModel | null;
  onNearbyAction?: (action: PanelAction) => void;
}) {
  const inputRef = React.useRef(input);
  React.useEffect(() => { inputRef.current = input; }, [input]);

  const textInputRef = React.useRef<TextInput>(null);
  const [inputHeight, setInputHeight] = React.useState(INPUT_MIN_HEIGHT);
  const [nearbyOpen, setNearbyOpen] = React.useState(false);

  // RN-web's onContentSizeChange doesn't fire on shrink — measure scrollHeight after collapsing to 0.
  React.useLayoutEffect(() => {
    if (!IS_WEB) return;
    const node = textInputRef.current as unknown as HTMLTextAreaElement | null;
    if (!node) return;
    node.style.height = '0px';
    const next = Math.min(
      INPUT_MAX_HEIGHT,
      Math.max(INPUT_MIN_HEIGHT, node.scrollHeight),
    );
    node.style.height = `${next}px`;
    setInputHeight((prev) => (prev === next ? prev : next));
  }, [input]);

  const handleChange = (t: string) => {
    inputRef.current = t;
    setInput(t);
  };

  const trimmed = input.trim();
  const hasText = trimmed.length > 0 && !locked;

  const sendText = (raw: string) => {
    const text = raw.trim();
    if (!text) return;
    onSend(text);
    inputRef.current = '';
    setInput('');
    setInputHeight(INPUT_MIN_HEIGHT);
    Keyboard.dismiss();
  };

  const submit = () => sendText(inputRef.current);

  const onNativeSubmit = (
    e: NativeSyntheticEvent<TextInputSubmitEditingEventData>,
  ) => {
    const fromEvent = e.nativeEvent.text ?? '';
    setTimeout(() => {
      const fromRef = inputRef.current ?? '';
      sendText(fromRef.length > fromEvent.length ? fromRef : fromEvent);
    }, 0);
  };

  const onContentSizeChange = (
    e: NativeSyntheticEvent<TextInputContentSizeChangeEventData>,
  ) => {
    if (IS_WEB) return;
    const next = Math.min(
      INPUT_MAX_HEIGHT,
      Math.max(INPUT_MIN_HEIGHT, e.nativeEvent.contentSize.height),
    );
    setInputHeight(next);
  };

  return (
    <View className="mx-5 mt-1.5 gap-2">
      {nearbyOpen && nearby && nearby.items.length > 0 ? (
        <Surface className="px-2.5 py-2 gap-1.5">
          {nearby.items.map((item) => (
            <View key={item.id} className="flex-row items-center gap-2 rounded-sm bg-canvas-inset px-2 py-2">
              <View className="flex-1 min-w-0">
                <Text numberOfLines={1} className="font-sans-semibold text-panel text-fg-default">
                  {item.title}
                </Text>
                {item.body ? (
                  <Text numberOfLines={1} className="font-sans text-caption text-fg-muted">
                    {item.body}
                  </Text>
                ) : null}
              </View>
              {item.action && onNearbyAction ? (
                <Pressable
                  onPress={() => {
                    setNearbyOpen(false);
                    onNearbyAction(item.action!);
                  }}
                  accessibilityRole="button"
                  accessibilityLabel={`${item.title} ${item.action.label}`}
                  className="min-w-14 items-center rounded-full border border-accent-fg bg-accent-muted px-3 py-1.5 active:opacity-80"
                >
                  <Text className="font-sans-semibold text-caption text-accent-fg">
                    {item.action.label}
                  </Text>
                </Pressable>
              ) : null}
            </View>
          ))}
        </Surface>
      ) : null}
      <Surface className="px-2.5 py-2 gap-1.5">
        {nearby ? (
          <Pressable
            onPress={() => setNearbyOpen((open) => !open)}
            accessibilityRole="button"
            accessibilityLabel={nearby.summary}
          >
            <Text className="font-sans-semibold text-caption text-fg-muted">
              {nearby.summary}
            </Text>
          </Pressable>
        ) : null}
        <View className="flex-row items-end gap-2">
          <TextInput
            ref={textInputRef}
            value={input}
            onChangeText={handleChange}
            onSubmitEditing={onNativeSubmit}
            onContentSizeChange={onContentSizeChange}
            editable={!locked}
            accessibilityState={{ disabled: locked }}
            placeholder={locked ? ko.composer.placeholderLocked : ko.composer.placeholder}
            placeholderTextColor={`${colors.fg.default}55`}
            returnKeyType="send"
            multiline
            submitBehavior="blurAndSubmit"
            textAlignVertical="top"
            className="font-sans-semibold text-panel text-fg-default flex-1 rounded-sm bg-canvas-inset px-3"
            style={{
              paddingTop: 10,
              paddingBottom: 10,
              height: inputHeight,
              borderWidth: 0,
              outlineWidth: 0,
              outlineStyle: 'none',
              ...(IS_WEB ? { scrollbarWidth: 'none' } : null),
            } as object}
          />
          {streaming ? (
            <StopButton onPress={onStop} />
          ) : (
            <SendButton enabled={hasText} onPress={submit} />
          )}
        </View>
      </Surface>
    </View>
  );
}
