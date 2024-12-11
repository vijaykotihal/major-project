// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract RideSharing {
    struct Ride {
        address passenger;
        address driver;
        uint256 distance;
        uint256 fare;
        bool completed;
        RideStatus status;
    }

    enum RideStatus { REQUESTED, ACCEPTED, COMPLETED, CANCELLED }

    mapping(uint256 => Ride) public rides;
    uint256 public rideCount;

    // Events with indexed parameters for better filtering
    event RideRequested(
        uint256 indexed rideId,
        address indexed passenger,
        address indexed driver,
        uint256 distance,
        uint256 fare
    );
    event RideAccepted(uint256 indexed rideId, address indexed driver, uint256 timestamp);
    event RideCompleted(uint256 indexed rideId, uint256 timestamp);
    event RideCancelled(uint256 indexed rideId, uint256 timestamp);
    event DebugRideStatus(uint256 indexed rideId, RideStatus status, address indexed user);

    function requestRide(uint256 distance) public payable returns (uint256) {
        require(msg.value > 0, "Fare must be greater than 0");
        require(distance > 0, "Distance must be greater than 0");
        
        rideCount++;
        rides[rideCount] = Ride({
            passenger: msg.sender,
            driver: address(0),
            distance: distance,
            fare: msg.value,
            completed: false,
            status: RideStatus.REQUESTED
        });

        // Emit event with all relevant information
        emit RideRequested(
            rideCount,
            msg.sender,
            address(0),
            distance,
            msg.value
        );
        
        return rideCount;
    }

    function acceptRide(uint256 rideId) public {
        Ride storage ride = rides[rideId];
        require(ride.passenger != address(0), "Ride does not exist");
        require(ride.status == RideStatus.REQUESTED, "Ride not available");
        require(ride.driver == address(0), "Ride already assigned");
        require(msg.sender != ride.passenger, "Passenger cannot be driver");

        ride.driver = msg.sender;
        ride.status = RideStatus.ACCEPTED;

        emit RideAccepted(rideId, msg.sender, block.timestamp);
    }

    function completeRide(uint256 rideId) public {
        Ride storage ride = rides[rideId];
        require(msg.sender == ride.driver, "Only driver can complete ride");
        require(ride.status == RideStatus.ACCEPTED, "Ride not in progress");
        require(!ride.completed, "Ride already completed");

        ride.completed = true;
        ride.status = RideStatus.COMPLETED;
        payable(ride.driver).transfer(ride.fare);

        emit RideCompleted(rideId, block.timestamp);
    }

    function cancelRide(uint256 rideId) public {
        Ride storage ride = rides[rideId];
        require(msg.sender == ride.passenger, "Only passenger can cancel");
        require(ride.status == RideStatus.REQUESTED, "Can only cancel requested rides");

        ride.status = RideStatus.CANCELLED;
        payable(ride.passenger).transfer(ride.fare);

        emit RideCancelled(rideId, block.timestamp);
    }

    function getUserCompletedRides(address user) public view returns (uint256[] memory) {
        uint256[] memory completedRides = new uint256[](rideCount);
        uint256 count = 0;

        for (uint256 i = 1; i <= rideCount; i++) {
            // Debugging events removed
            if (rides[i].passenger != address(0) &&
                (rides[i].passenger == user || rides[i].driver == user) &&
                rides[i].status == RideStatus.COMPLETED) {
                completedRides[count] = i;
                count++;
            }
        }

        uint256[] memory result = new uint256[](count);
        for (uint256 i = 0; i < count; i++) {
            result[i] = completedRides[i];
        }

        return result;
    }


    function getAvailableRides() public view returns (uint256[] memory) {
        uint256[] memory availableRides = new uint256[](rideCount);
        uint256 count = 0;
        
        for (uint256 i = 1; i <= rideCount; i++) {
            if (rides[i].passenger != address(0) && // Ensure ride exists
                rides[i].status == RideStatus.REQUESTED) {
                availableRides[count] = i;
                count++;
            }
        }
        
        uint256[] memory result = new uint256[](count);
        for (uint256 i = 0; i < count; i++) {
            result[i] = availableRides[i];
        }
        
        return result;
    }

    function getUserActiveRides(address user) public view returns (uint256[] memory) {
        uint256[] memory activeRides = new uint256[](rideCount);
        uint256 count = 0;
        
        for (uint256 i = 1; i <= rideCount; i++) {
            if (rides[i].passenger != address(0) && // Ensure ride exists
                (rides[i].passenger == user || rides[i].driver == user) &&
                rides[i].status == RideStatus.ACCEPTED) {
                activeRides[count] = i;
                count++;
            }
        }
        
        uint256[] memory result = new uint256[](count);
        for (uint256 i = 0; i < count; i++) {
            result[i] = activeRides[i];
        }
        
        return result;
    }

    function getRide(uint256 rideId) public view returns (
        address passenger,
        address driver,
        uint256 distance,
        RideStatus status,
        uint256 fare
    ) {
        Ride storage ride = rides[rideId];
        return (
            ride.passenger,
            ride.driver,
            ride.distance,
            ride.status,
            ride.fare
        );
    }

    receive() external payable {}
}
