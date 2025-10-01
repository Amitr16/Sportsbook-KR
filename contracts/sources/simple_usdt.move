/// Simple USDT Token for Sportsbook Platform
/// Minimal implementation to avoid compiler issues

module sportsbook_platform::simple_usdt {
    use std::string;
    use std::signer;
    use aptos_framework::coin::{Self, BurnCapability, FreezeCapability, MintCapability};

    /// USDT token struct
    struct SimpleUSDT {}

    /// Capabilities for managing the token
    struct Capabilities has key {
        mint_cap: MintCapability<SimpleUSDT>,
        burn_cap: BurnCapability<SimpleUSDT>,
        freeze_cap: FreezeCapability<SimpleUSDT>,
    }

    /// Initialize the USDT token
    public entry fun initialize(admin: &signer) {
        let (burn_cap, freeze_cap, mint_cap) = coin::initialize<SimpleUSDT>(
            admin,
            string::utf8(b"Simple USDT"),
            string::utf8(b"SUSDT"),
            6, // 6 decimals
            true, // monitor_supply
        );

        move_to(admin, Capabilities {
            mint_cap,
            burn_cap,
            freeze_cap,
        });
    }

    /// Mint USDT tokens
    public entry fun mint_usdt(
        admin: &signer,
        to: address,
        amount: u64
    ) acquires Capabilities {
        let capabilities = borrow_global<Capabilities>(signer::address_of(admin));
        let coins = coin::mint<SimpleUSDT>(amount, &capabilities.mint_cap);
        coin::deposit<SimpleUSDT>(to, coins);
    }

    /// Transfer USDT between wallets
    public entry fun transfer_usdt(
        from: &signer,
        to: address,
        amount: u64
    ) {
        coin::transfer<SimpleUSDT>(from, to, amount);
    }

    /// Get token balance
    public fun get_balance(addr: address): u64 {
        coin::balance<SimpleUSDT>(addr)
    }
}
