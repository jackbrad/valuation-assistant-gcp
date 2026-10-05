import type * as React from 'react';
export interface IconProps { name: string; size?: number; label?: string; className?: string }
export declare function Icon(props: IconProps): React.ReactElement;
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'sm' | 'md' | 'lg'; icon?: string; iconEnd?: string }
export declare function Button(props: ButtonProps): React.ReactElement;
export interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> { label?: string; help?: string; error?: string; icon?: string }
export declare function TextField(props: TextFieldProps): React.ReactElement;
export interface PromptBoxProps { onSubmit?: (text: string) => void; placeholder?: string; defaultValue?: string; rows?: number; label?: string; meta?: string; tools?: React.ReactNode; busy?: boolean; className?: string }
export declare function PromptBox(props: PromptBoxProps): React.ReactElement;
export interface TabItem { value: string; label: string; icon?: string; count?: number }
export interface TabsProps { items: TabItem[]; value?: string; defaultValue?: string; onChange?: (value: string) => void; label?: string; className?: string }
export declare function Tabs(props: TabsProps): React.ReactElement;
export interface SwitchProps { label?: string; checked?: boolean; defaultChecked?: boolean; onChange?: (next: boolean) => void; disabled?: boolean; className?: string }
export declare function Switch(props: SwitchProps): React.ReactElement;
export interface CardProps extends React.HTMLAttributes<HTMLElement> { eyebrow?: string; title?: string; actions?: React.ReactNode; footer?: React.ReactNode; flat?: boolean }
export declare function Card(props: CardProps): React.ReactElement;
export interface MetricProps { label: string; value: string; unit?: string; trend?: 'up' | 'down' | 'neutral'; good?: boolean; delta?: string; className?: string }
export declare function Metric(props: MetricProps): React.ReactElement;
export interface TableColumn<R = any> { key: string; label: string; align?: 'right'; mono?: boolean; render?: (row: R) => React.ReactNode }
export interface TableProps<R = any> { columns: TableColumn<R>[]; rows: R[]; caption?: string; className?: string }
export declare function Table(props: TableProps): React.ReactElement;
export interface BadgeProps { tone?: 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'new'; icon?: string | false; children?: React.ReactNode; className?: string }
export declare function Badge(props: BadgeProps): React.ReactElement;
export interface BannerProps { tone?: 'info' | 'success' | 'warning' | 'danger'; title?: string; icon?: string; action?: React.ReactNode; children?: React.ReactNode; className?: string }
export declare function Banner(props: BannerProps): React.ReactElement;
export interface TopBarProps { product: string; context?: string; markIcon?: string; actions?: React.ReactNode; className?: string }
export declare function TopBar(props: TopBarProps): React.ReactElement;
declare global { interface Window { Clearline: { Icon: typeof Icon; Button: typeof Button; TextField: typeof TextField; PromptBox: typeof PromptBox; Tabs: typeof Tabs; Switch: typeof Switch; Card: typeof Card; Metric: typeof Metric; Table: typeof Table; Badge: typeof Badge; Banner: typeof Banner; TopBar: typeof TopBar } } }
