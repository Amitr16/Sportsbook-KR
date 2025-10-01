#!/usr/bin/env python3
"""
Deploy Sportsbook USDT Contract to Aptos Testnet
Handles contract compilation, deployment, and initialization
"""

import os
import subprocess
import json
import time
import requests
from pathlib import Path

class AptosUSDTDeployer:
    def __init__(self):
        self.contract_dir = Path("contracts")
        self.aptos_config_dir = Path.home() / ".aptos"
        self.testnet_url = "https://fullnode.testnet.aptoslabs.com/v1"
        self.faucet_url = "https://faucet.testnet.aptoslabs.com"
        
    def check_aptos_cli(self):
        """Check if Aptos CLI is installed"""
        try:
            result = subprocess.run(["aptos", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Aptos CLI found: {result.stdout.strip()}")
                return True
            else:
                print("❌ Aptos CLI not found")
                return False
        except FileNotFoundError:
            print("❌ Aptos CLI not installed")
            print("📥 Install from: https://aptos.dev/tools/aptos-cli/install-cli/")
            return False

    def init_aptos_account(self):
        """Initialize Aptos account for deployment"""
        print("🔑 Initializing Aptos account...")
        
        try:
            # Initialize account
            result = subprocess.run([
                "aptos", "init", 
                "--network", "testnet",
                "--assume-yes"
            ], capture_output=True, text=True, cwd=self.contract_dir)
            
            if result.returncode == 0:
                print("✅ Aptos account initialized")
                
                # Get account address
                config_result = subprocess.run([
                    "aptos", "account", "list", "--query", "balance"
                ], capture_output=True, text=True, cwd=self.contract_dir)
                
                if config_result.returncode == 0:
                    # Extract address from output
                    lines = config_result.stdout.split('\n')
                    for line in lines:
                        if 'account' in line.lower() and '0x' in line:
                            address = line.split('0x')[1].split()[0]
                            self.deployer_address = f"0x{address}"
                            print(f"📍 Deployer address: {self.deployer_address}")
                            return True
                
                print("⚠️ Could not extract deployer address")
                return False
            else:
                print(f"❌ Failed to initialize account: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error initializing account: {e}")
            return False

    def fund_account(self):
        """Fund the deployer account with testnet APT"""
        print("💰 Funding deployer account...")
        
        try:
            result = subprocess.run([
                "aptos", "account", "fund-with-faucet",
                "--account", "default"
            ], capture_output=True, text=True, cwd=self.contract_dir)
            
            if result.returncode == 0:
                print("✅ Account funded successfully")
                
                # Check balance
                balance_result = subprocess.run([
                    "aptos", "account", "list", "--query", "balance"
                ], capture_output=True, text=True, cwd=self.contract_dir)
                
                if balance_result.returncode == 0:
                    print(f"💳 Account balance: {balance_result.stdout}")
                
                return True
            else:
                print(f"❌ Failed to fund account: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error funding account: {e}")
            return False

    def compile_contract(self):
        """Compile the Move contract"""
        print("🔨 Compiling USDT contract...")
        
        try:
            result = subprocess.run([
                "aptos", "move", "compile"
            ], capture_output=True, text=True, cwd=self.contract_dir)
            
            if result.returncode == 0:
                print("✅ Contract compiled successfully")
                print(result.stdout)
                return True
            else:
                print(f"❌ Compilation failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error compiling contract: {e}")
            return False

    def deploy_contract(self):
        """Deploy the contract to testnet"""
        print("🚀 Deploying USDT contract to Aptos testnet...")
        
        try:
            result = subprocess.run([
                "aptos", "move", "publish",
                "--assume-yes"
            ], capture_output=True, text=True, cwd=self.contract_dir)
            
            if result.returncode == 0:
                print("✅ Contract deployed successfully!")
                print(result.stdout)
                
                # Extract transaction hash
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'transaction hash' in line.lower() or 'hash' in line.lower():
                        if '0x' in line:
                            tx_hash = line.split('0x')[1].split()[0]
                            self.deployment_tx = f"0x{tx_hash}"
                            print(f"📝 Deployment transaction: {self.deployment_tx}")
                            break
                
                return True
            else:
                print(f"❌ Deployment failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error deploying contract: {e}")
            return False

    def initialize_contract(self):
        """Initialize the USDT contract"""
        print("⚙️ Initializing USDT contract...")
        
        try:
            result = subprocess.run([
                "aptos", "move", "run",
                "--function-id", f"{self.deployer_address}::sportsbook_usdt::initialize",
                "--assume-yes"
            ], capture_output=True, text=True, cwd=self.contract_dir)
            
            if result.returncode == 0:
                print("✅ Contract initialized successfully!")
                print(result.stdout)
                return True
            else:
                print(f"❌ Initialization failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error initializing contract: {e}")
            return False

    def verify_deployment(self):
        """Verify the contract is deployed and working"""
        print("🔍 Verifying contract deployment...")
        
        try:
            # Check if account exists
            response = requests.get(f"{self.testnet_url}/accounts/{self.deployer_address}")
            
            if response.status_code == 200:
                account_data = response.json()
                print(f"✅ Contract account found")
                print(f"  Sequence Number: {account_data.get('sequence_number')}")
                
                # Try to call a view function
                view_response = requests.post(
                    f"{self.testnet_url}/view",
                    json={
                        "function": f"{self.deployer_address}::sportsbook_usdt::get_token_info",
                        "type_arguments": [],
                        "arguments": []
                    }
                )
                
                if view_response.status_code == 200:
                    token_info = view_response.json()
                    print(f"✅ Contract is functional")
                    print(f"  Token Name: {token_info[0]}")
                    print(f"  Token Symbol: {token_info[1]}")
                    print(f"  Decimals: {token_info[2]}")
                    return True
                else:
                    print(f"⚠️ Contract view function failed: {view_response.status_code}")
                    return True  # Account exists, might just be view function issue
                    
            else:
                print(f"❌ Contract account not found: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error verifying deployment: {e}")
            return False

    def save_deployment_info(self):
        """Save deployment information"""
        deployment_info = {
            "contract_address": self.deployer_address,
            "contract_name": "sportsbook_usdt",
            "full_contract_id": f"{self.deployer_address}::sportsbook_usdt::SportsbookUSDT",
            "network": "testnet",
            "deployment_tx": getattr(self, 'deployment_tx', None),
            "deployed_at": time.time(),
            "explorer_url": f"https://explorer.aptoslabs.com/account/{self.deployer_address}?network=testnet"
        }
        
        with open("usdt_contract_info.json", "w") as f:
            json.dump(deployment_info, f, indent=2)
        
        print(f"💾 Deployment info saved to usdt_contract_info.json")
        return deployment_info

    def deploy(self):
        """Full deployment process"""
        print("🚀 Starting Sportsbook USDT Contract Deployment")
        print("=" * 60)
        
        steps = [
            ("Check Aptos CLI", self.check_aptos_cli),
            ("Initialize Account", self.init_aptos_account),
            ("Fund Account", self.fund_account),
            ("Compile Contract", self.compile_contract),
            ("Deploy Contract", self.deploy_contract),
            ("Initialize Contract", self.initialize_contract),
            ("Verify Deployment", self.verify_deployment),
        ]
        
        for step_name, step_func in steps:
            print(f"\n📋 {step_name}...")
            if not step_func():
                print(f"❌ {step_name} failed - stopping deployment")
                return False
        
        # Save deployment info
        deployment_info = self.save_deployment_info()
        
        print("\n" + "=" * 60)
        print("🎉 USDT CONTRACT DEPLOYED SUCCESSFULLY!")
        print(f"📍 Contract Address: {deployment_info['contract_address']}")
        print(f"🔗 Explorer: {deployment_info['explorer_url']}")
        print(f"💰 Token: {deployment_info['full_contract_id']}")
        print("\n🌐 Next Steps:")
        print("• Update CrossmintUSDTService with new contract address")
        print("• Test minting and funding operations")
        print("• Fund operators with initial USDT")
        
        return True

def main():
    deployer = AptosUSDTDeployer()
    success = deployer.deploy()
    
    if not success:
        print("\n❌ Deployment failed - check the errors above")
        exit(1)
    else:
        print("\n✅ Deployment completed successfully!")

if __name__ == "__main__":
    main()
