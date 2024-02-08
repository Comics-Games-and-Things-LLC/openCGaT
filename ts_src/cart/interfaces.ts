import {step} from "../checkout/components/CheckoutStep";

export enum ButtonStyles {
    BUTTON_STYLE_SOLD_OUT = 1,
    BUTTON_STYLE_BACKORDER = 2,
    BUTTON_STYLE_GOOD = 3,
}

export interface IButtonStatus {
    text: string;
    enabled: boolean;
    style?: ButtonStyles;
}

export interface IUser {
    username?: string;
    email?: string;
}

export interface IItem {
    id: number;
    partner: IPartner;
    product: IProduct
    price: number;
    type: string;
    default_price: number;
    backorders_enabled: boolean;
    is_preorder: boolean;
    is_pay_what_you_want: boolean;
    inventory: number;
    button_status: IButtonStatus;
}

export interface IRowProps {
    pos: boolean
    item: IItem
    key: number
    quantity: number
    open: boolean
    price: number
    status: string
    price_per_unit_override: number
    estimated_cost: number
    full: boolean
    show_status_col: boolean
    description: string
    discount_code_message: string
    show_cost_col?: boolean;
}

export interface ICart {
    loaded?: boolean;
    status: string;
    lines: IRowProps[];
    open: boolean;
    id: number;
    site: string;

    subtotal: string;
    final_tax: string;
    final_ship: string;
    final_total: string;
    estimated_tax: string;
    estimated_total: string;
    cancelled_amount: string;
    total_paid: string;
    cash_paid: string;
    owner_info?: string;
    username?: string;
    email?: string;
    shipping_address: IAddress;
    billing_address: IAddress;
    payment_partner?: IPartner;
    is_shipping_required: boolean;
    in_store_pickup_only: boolean;
    available_pickup_partners: IPartner[];
    pickup_partner?: IPartner;
    is_free: boolean;
    is_account_required: boolean;
    delivery_method: string;
    payment_method: string;
    show_status_col: boolean;

    disclaimer: string;

    completed_steps: step[];
    ready_steps: step[];
    address_error?: any;

    discount_code: string;
    discount_code_message: string

}

export interface IProduct {
    slug: any;
    id: number;
    name: string;
}

export interface IPartner {
    name: string;
    slug: string;
    id: string;
    address_and_hours_info?: string;
}

export interface IPOSProps {
    active_cart?: ICart;
    open_carts?: [ICart];
    pay_in_store_carts?: [ICart];
    pickup_carts?: [ICart];
    url: string;
}

export interface IAddress {
    id: number
    first_name: string
    last_name?: string
    line1: string
    line2: string
    line3: string
    line4: string
    state: string
    country: string
    postcode: string
    phone_number: string
}