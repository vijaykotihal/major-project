import streamlit as st
from web3 import Web3
from web3.exceptions import ContractLogicError, InvalidAddress
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import folium
from streamlit_folium import st_folium
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import requests
import polyline 


# Load environment variables
load_dotenv()


class CarpoolingApp:
    def __init__(self):
        self.setup_blockchain_connection()
        self.setup_session_state()
        self.load_contract()

    def setup_blockchain_connection(self):
        """Initialize blockchain connection with error handling"""
        self.ganache_url = os.getenv("BLOCKCHAIN_URL", "http://127.0.0.1:8545")
        self.web3 = Web3(Web3.HTTPProvider(self.ganache_url))

        if not self.web3.is_connected():
            st.error("🔴 Blockchain connection failed. Please check if:")
            st.error("1. Ganache is running")
            st.error("2. The URL is correct")
            st.error("3. Your network connection is stable")
            st.stop()
        else:
            try:
                self.accounts = self.web3.eth.accounts
                if not self.accounts:
                    st.error("No accounts available in Ganache")
                    st.stop()

                # Default account setup
                self.web3.eth.default_account = self.accounts[0]
                st.sidebar.success("🟢 Connected to blockchain")
            except Exception as e:
                st.error(f"Error fetching accounts: {str(e)}")
                st.stop()

    def setup_session_state(self):
        """Initialize session state variables"""
        defaults = {
            "authenticated": False,
            "account": None,
            "user_type": None,
            "users": {},  # Store user data
            "messages": {},
            "active_chat": None,
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def register_tab(self):
        """Handle user registration"""
        st.header("👤 Sign Up")

        if st.session_state.authenticated:
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("Full Name", placeholder="Enter your full name")
                email = st.text_input("Email", placeholder="Enter your email")
                
            with col2:
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                role = st.radio("Select Role", options=["Passenger", "Driver"])

            if st.button("Sign Up"):
                if not all([name, email, password]):
                    st.error("Please fill in all fields")
                    return
                    
                if "@" not in email or "." not in email.split("@")[1]:
                    st.error("Please enter a valid email address")
                    return
                    
                if email in st.session_state.users:
                    st.error("Email already registered")
                    return
                    
                # Store user data
                st.session_state.users[email] = {
                    "name": name,
                    "password": password,  # In production, this should be hashed
                    "role": role,
                    "wallet": st.session_state.account
                }
                
                st.success("✅ Registration successful! Please proceed to Login")
        else:
            st.warning("Please connect your wallet first")

    def login_tab(self):
        """Handle user login"""
        st.header("🔓 Login")

        if st.session_state.authenticated:
            email = st.text_input("Email", placeholder="Enter your email",key="login_mail")
            password = st.text_input("Password", type="password", placeholder="Enter your password",key="login_pass")

            if st.button("Login"):
                if not email or not password:
                    st.error("Please fill in all fields")
                    return

                # Check if user exists
                if email not in st.session_state.users:
                    st.error("Email not found")
                    return

                user = st.session_state.users[email]
                
                # Verify password
                if user["password"] != password:
                    st.error("Incorrect password")
                    return

                # Verify wallet
                if user["wallet"] != st.session_state.account:
                    st.error("Please use the wallet address associated with this account")
                    return

                # Set session state
                st.session_state.user_type = user["role"]
                st.session_state.current_user = user
                
                st.success(f"✅ Welcome back, {user['name']}!")
                
                # Force a rerun to update the UI
                st.rerun()
        else:
            st.warning("Please connect your wallet first")

    def load_contract(self):
        """Load smart contract with error handling"""
        try:
            self.contract_address = os.getenv("CONTRACT_ADDRESS")
            contract_path = os.getenv("CONTRACT_PATH", "build/contracts/RideSharing.json")

            with open(contract_path, "r") as file:
                contract_data = json.load(file)

            self.contract_abi = contract_data["abi"]
            self.contract = self.web3.eth.contract(
                address=self.contract_address, abi=self.contract_abi
            )
        except (FileNotFoundError, json.JSONDecodeError) as e:
            st.error(f"Error loading contract: {str(e)}")
            st.stop()


    def chat_tab(self):
   # """Handle chat functionality between drivers and passengers"""
            st.header("💬 Chat Between Driver and Passenger")

            if not st.session_state.authenticated:
                    st.warning("Please connect your wallet to use the chat feature")
                    return

            try:
                    # Get active rides for the current user
                    active_rides = self.contract.functions.getUserActiveRides(
                        st.session_state.account
                    ).call()

                    if not active_rides:
                        st.info("No active rides found. You can chat once you have an active ride.")
                        return

                    for ride_id in active_rides:
                        ride = self.get_ride_details(ride_id)
                        if ride:
                            # Determine if user is the driver or passenger
                            is_driver = ride["driver"].lower() == st.session_state.account.lower()
                            chat_partner = ride["passenger"] if is_driver else ride["driver"]

                            # Chat interface for each active ride
                            with st.expander(f"Chat - Ride #{ride_id}", expanded=True):
                                # Initialize chat history if not already set
                                if f"ride_{ride_id}_messages" not in st.session_state:
                                    st.session_state[f"ride_{ride_id}_messages"] = []

                                # Display chat history
                                chat_container = st.container()
                                for message in st.session_state[f"ride_{ride_id}_messages"]:
                                    sender, msg, timestamp = message
                                    is_user = sender.lower() == st.session_state.account.lower()
                                    align = "right" if is_user else "left"
                                    bg_color = "#DCF8C6" if is_user else "#F1F0F0"  # WhatsApp-style colors
                                    text_color = "#0B6623" if is_user else "#333333"  # Dark green for user

                                    with chat_container:
                                        st.markdown(
                                             f"""
                                                <div style="text-align: {align}; background-color: {bg_color}; 
                                                            padding: 10px; border-radius: 10px; margin: 5px;
                                                            color: {text_color}; font-family: Arial, sans-serif;">
                                                    <strong>{'You' if is_user else chat_partner[:6] + '...' + chat_partner[-4:]}</strong><br>
                                                    {msg}<br>
                                                    <small style="color: grey;">{timestamp}</small>
                                                </div>
                                                """,
                                            unsafe_allow_html=True,
                                        )

                                # Input for new messages
                                message = st.text_input(
                                    f"Send a message (Ride #{ride_id})",
                                    key=f"input_{ride_id}",
                                    placeholder="Type your message here...",
                                )
                                if st.button(f"Send (Ride #{ride_id})"):
                                    if message.strip():
                                        # Add new message to chat history
                                        st.session_state[f"ride_{ride_id}_messages"].append(
                                            (
                                                st.session_state.account,
                                                message.strip(),
                                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            )
                                        )
                                        st.rerun()

            except Exception as e:
                st.error(f"Error loading chat: {str(e)}")


    def validate_wallet_address(self, address):
        """Validate the format of a wallet address"""
        try:
            return self.web3.is_address(address) and self.web3.is_checksum_address(address)
        except InvalidAddress:
            return False

    def handle_authentication(self):
        """Handle user authentication and wallet connection"""
        st.sidebar.title("👤 User Authentication")

        if not st.session_state.authenticated:
            selected_account = st.sidebar.selectbox(
                "Select Ganache Account",
                self.accounts,
                format_func=lambda x: f"{x[:6]}...{x[-4:]}"
            )
            if st.sidebar.button("Connect Wallet"):
                st.session_state.account = selected_account
                st.session_state.authenticated = True
                st.rerun()
        else:
            account = st.session_state.account
            balance = self.web3.from_wei(self.web3.eth.get_balance(account), "ether")
            st.sidebar.success(f"✅ Connected to: {account[:6]}...{account[-4:]}")
            st.sidebar.info(f"💰 Balance: {balance:.4f} ETH")
            
            # Show logout button only if user is logged in
            if st.session_state.user_type:
                if st.sidebar.button("Logout"):
                    st.session_state.user_type = None
                    st.session_state.current_user = None
                    st.rerun()
                    
            # Show disconnect wallet button
            if st.sidebar.button("Disconnect Wallet"):
                st.session_state.authenticated = False
                st.session_state.account = None
                st.session_state.user_type = None
                st.session_state.current_user = None
                st.rerun()

    def get_ride_details(self, ride_id):
        """Fetch ride details from the blockchain"""
        try:
            ride = self.contract.functions.getRide(ride_id).call()
            return {
                "passenger": ride[0],
                "driver": ride[1],
                "distance": ride[2],
                "status": ride[3],
                "fare": ride[4],
            }
        except ContractLogicError:
            return None
        except Exception as e:
            st.error(f"Error fetching ride details: {str(e)}")
            return None



   # def request_ride_tab(self):
 # To decode polylines into coordinates

    def request_ride_tab(self):
        """Handle ride requests with road-based routing"""
        st.header("🚗 Request a Ride")

        # Initialize geolocator
        geolocator = Nominatim(user_agent="carpooling_app")

        def geocode_location(location_name):
            """Helper function to geocode a location name into coordinates"""
            try:
                location = geolocator.geocode(location_name)
                if location:
                    return location.latitude, location.longitude
                else:
                    return None
            except GeocoderTimedOut:
                st.error("Geocoding request timed out. Please try again.")
                return None

        # Initialize session state for locations if not set
        if "pickup_coords" not in st.session_state:
            st.session_state["pickup_coords"] = None
        if "dropoff_coords" not in st.session_state:
            st.session_state["dropoff_coords"] = None

        # User inputs for pickup and drop-off locations
        pickup_location = st.text_input("Enter Pickup Location", placeholder="e.g., Connaught Place, Delhi")
        dropoff_location = st.text_input("Enter Drop-off Location", placeholder="e.g., Chandigarh, Punjab")

        if st.button("Show Locations on Map"):
            if not pickup_location or not dropoff_location:
                st.error("Both pickup and drop-off locations are required!")
            else:
                # Geocode the locations and store in session state
                pickup_coords = geocode_location(pickup_location)
                dropoff_coords = geocode_location(dropoff_location)

                if pickup_coords and dropoff_coords:
                    st.session_state["pickup_coords"] = pickup_coords
                    st.session_state["dropoff_coords"] = dropoff_coords
                else:
                    st.error("Could not geocode one or both locations. Please check the input.")

        # Only display the map if locations are available in session state
        if st.session_state["pickup_coords"] and st.session_state["dropoff_coords"]:
            # Use OpenRouteService to get the route
            ors_api_key = "5b3ce3597851110001cf6248f7450cb5301c4b21ba636260adaf9513"  # Replace with your API key
            route_url = "https://api.openrouteservice.org/v2/directions/driving-car"
            headers = {"Authorization": ors_api_key, "Content-Type": "application/json"}
            payload = {
                "coordinates": [
                    [st.session_state["pickup_coords"][1], st.session_state["pickup_coords"][0]],
                    [st.session_state["dropoff_coords"][1], st.session_state["dropoff_coords"][0]],
                ]
            }

            try:
                response = requests.post(route_url, json=payload, headers=headers)
                response.raise_for_status()
                route_data = response.json()

                # Decode the polyline into coordinates
                route_geometry = route_data["routes"][0]["geometry"]
                route_coords = polyline.decode(route_geometry)

                # Create map centered at pickup location
                m = folium.Map(location=st.session_state["pickup_coords"], zoom_start=8)

                # Add markers for pickup and drop-off locations
                folium.Marker(
                    location=st.session_state["pickup_coords"],
                    popup="Pickup Location",
                    icon=folium.Icon(color="green"),
                ).add_to(m)

                folium.Marker(
                    location=st.session_state["dropoff_coords"],
                    popup="Drop-off Location",
                    icon=folium.Icon(color="red"),
                ).add_to(m)

                # Add the route as a PolyLine
                folium.PolyLine(route_coords, color="blue", weight=5).add_to(m)

                # Display the map in Streamlit
                st_folium(m, width=700, height=500)

                # Calculate distance and fare
                distance_km = route_data["routes"][0]["summary"]["distance"] / 1000  # Convert to km
                fare = self.web3.to_wei(distance_km * 0.1, "ether")

                st.info(f"Distance: {distance_km:.2f} km")
                st.info(f"Estimated fare: {self.web3.from_wei(fare, 'ether')} ETH")

                if st.button("Request Ride"):
                    try:
                        distance_meters = int(distance_km * 1000)
                        tx = self.contract.functions.requestRide(distance_meters).transact({
                            "from": st.session_state.account,
                            "value": fare,
                            "gas": 300000
                        })

                        receipt = self.web3.eth.wait_for_transaction_receipt(tx)
                        st.write("Transaction receipt:", receipt)

                        # Decode the event
                        events = self.contract.events.RideRequested().process_receipt(receipt)
                        if events:
                            ride_id = events[0]["args"]["rideId"]
                            st.success(f"✅ Ride requested successfully!")
                            st.info(f"🎫 Your Ride ID: {ride_id}")
                        else:
                            st.error("❌ Event was emitted but could not be decoded.")

                    except Exception as e:
                        st.error(f"❌ Error requesting ride: {str(e)}")


            except Exception as e:
                st.error(f"❌ Error requesting ride: {str(e)}")




    def accept_ride_tab(self):
        """Handle ride acceptance by drivers"""
        st.header("🚘 Accept a Ride")

        try:
            available_rides = self.contract.functions.getAvailableRides().call()
            if not available_rides:
                st.info("No rides available at the moment")
                return

            for ride_id in available_rides:
                ride = self.get_ride_details(ride_id)
                if ride:
                    with st.expander(f"Ride #{ride_id}"):
                        st.write(f"Distance: {ride['distance']} km")
                        st.write(f"Fare: {self.web3.from_wei(ride['fare'], 'ether')} ETH")
                        if st.button(f"Accept Ride #{ride_id}"):
                            try:
                                tx = self.contract.functions.acceptRide(ride_id).transact(
                                    {"from": st.session_state.account}
                                )
                                self.web3.eth.wait_for_transaction_receipt(tx)
                                st.success(f"✅ Ride #{ride_id} accepted successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error accepting ride: {str(e)}")
        except Exception as e:
            st.error(f"Error loading available rides: {str(e)}")

    def complete_ride_tab(self):
        """Handle ride completion"""
        st.header("🏁 Complete Ride")

        try:
            active_rides = self.contract.functions.getUserActiveRides(
                st.session_state.account
            ).call()
            if not active_rides:
                st.info("No active rides found")
                return

            for ride_id in active_rides:
                ride = self.get_ride_details(ride_id)
                if ride:
                    with st.expander(f"Active Ride #{ride_id}"):
                        st.write(f"Distance: {ride['distance']} km")
                        st.write(f"Fare: {self.web3.from_wei(ride['fare'], 'ether')} ETH")
                        if st.button(f"Complete Ride #{ride_id}"):
                            try:
                                tx = self.contract.functions.completeRide(ride_id).transact(
                                    {"from": st.session_state.account}
                                )
                                self.web3.eth.wait_for_transaction_receipt(tx)
                                st.success(f"✅ Ride #{ride_id} completed successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error completing ride: {str(e)}")
        except Exception as e:
            st.error(f"Error loading active rides: {str(e)}")

    def show_ride_history(self):
        """Display ride history for the user"""
        st.header("📖 Ride History")

        try:
            completed_rides = self.contract.functions.getUserCompletedRides(
                st.session_state.account
            ).call()
            if not completed_rides:
                st.info("No ride history found")
                return

            for ride_id in completed_rides:
                ride = self.get_ride_details(ride_id)
                if ride:
                    with st.expander(f"Ride #{ride_id}"):
                        st.write(f"Distance: {ride['distance']} km")
                        st.write(f"Fare: {self.web3.from_wei(ride['fare'], 'ether')} ETH")
                        st.write(f"Status: {'Completed' if ride['status'] else 'Pending'}")
        except Exception as e:
            st.error(f"Error loading ride history: {str(e)}")



    def run(self):
        """Main application loop"""
        st.title("🚗 Blockchain-Based P2P Carpooling")
        st.markdown("---")

        self.handle_authentication()

        if st.session_state.authenticated:
            if not st.session_state.user_type:
                # Show auth tabs when user is not logged in
                tab1, tab2 = st.tabs(["Sign Up", "Login"])
                
                with tab1:
                    self.register_tab()
                with tab2:
                    self.login_tab()
            else:
                # Show appropriate tabs based on user type
                if st.session_state.user_type == "Passenger":
                    tab1, tab2, tab3 = st.tabs([
                        "Request Ride",
                        "Ride History",
                        "Chat"
                    ])
                    
                    with tab1:
                        self.request_ride_tab()
                    with tab2:
                        self.show_ride_history()
                    with tab3:
                        self.chat_tab()
                        
                elif st.session_state.user_type == "Driver":
                    tab1, tab2, tab3, tab4 = st.tabs([
                        "Accept Ride",
                        "Complete Ride",
                        "Ride History",
                        "Chat"
                    ])
                    
                    with tab1:
                        self.accept_ride_tab()
                    with tab2:
                        self.complete_ride_tab()
                    with tab3:
                        self.show_ride_history()
                    with tab4:
                        self.chat_tab()
        else:
            st.warning("Please connect your wallet to proceed")



if __name__ == "__main__":
    app = CarpoolingApp()
    app.run()
