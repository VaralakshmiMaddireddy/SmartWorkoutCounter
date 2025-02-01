let bicepRange; // Declare bicepRange globally
let alertShown = false; // Flag for alerting user
let exerciseIntervalId; // Store interval ID for polling
let totalReps = 0; // Track total reps for the graph
let exerciseData = []; // Array to store exercise data
let workoutData = []; // Array to store workout data

// Load previous workout data from the server
function loadWorkoutData() {
    fetch('/workout_data')
        .then(response => response.json())
        .then(data => {
            workoutData = data; // Load workout data from the server
            renderWorkoutGraph(); // Render the workout graph with loaded data
        })
        .catch((error) => {
            console.error('Error loading workout data:', error);
        });
}

// Sign-in form submission
// Sign-in form submission
document.getElementById('signin-form').addEventListener('submit', function (e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    // Assuming a successful login
    localStorage.setItem('username', username);
    localStorage.setItem('password', password);
    document.getElementById('signin-form').style.display = 'none'; // Hide the sign-in form
    document.getElementById('fitness-history').style.display = 'block'; // Show fitness history section
});


// Fetch bicep range based on fitness level
document.getElementById('fetch-fitness').addEventListener('click', function () {
    const fitnessLevel = document.getElementById('fitness-level').value;

    // Set bicep range based on selected fitness level
    switch (fitnessLevel) {
        case 'beginner':
            bicepRange = 5; // Example bicep range for beginner
            break;
        case 'intermediate':
            bicepRange = 10; // Example bicep range for intermediate
            break;
        case 'advanced':
            bicepRange = 15; // Example bicep range for advanced
            break;
        default:
            bicepRange = 0; // Default if no valid fitness level selected
            break;
    }

    // Display fitness level and bicep range
    document.getElementById('fitness-level-output').textContent = fitnessLevel.charAt(0).toUpperCase() + fitnessLevel.slice(1);
    document.getElementById('biceps-range').textContent = bicepRange;
    document.getElementById('fitness-result').style.display = 'block';
    document.getElementById('start-button').style.display = 'block'; // Show start button
});

// Start exercise
document.getElementById('start-button').addEventListener('click', function () {
    fetch('/start_exercise', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log('Exercise started:', data);
            document.getElementById('fitness-history').style.display = 'none';
            document.getElementById('exercise-interface').style.display = 'block';
            document.getElementById('exercise-graph-container').style.display = 'block'; // Show graph container

            // Start polling for the rep count every 1 second
            exerciseIntervalId = setInterval(() => {
                fetch('/status')  // GET request to fetch current rep count and stage
                    .then(response => response.json())
                    .then(statusData => {
                        totalReps = statusData.counter; // Update total reps
                        document.getElementById('total-count').textContent = `Total Reps: ${totalReps}`;
                        document.getElementById('current-stage').textContent = `Current Stage: ${statusData.stage}`;

                        // Check if total count exceeds bicep range
                        if (totalReps > bicepRange) {
                            if (!alertShown) {
                                alert('Warning: You have exceeded your recommended bicep range! Consider stopping the exercise.');
                                alertShown = true; // Set flag to true after alert is shown
                            }
                        } else {
                            alertShown = false; // Reset the flag if condition is no longer met
                        }

                        // Store exercise data with timestamp
                        const timestamp = new Date().toLocaleString();
                        exerciseData.push({ timestamp, totalReps });
                        renderGraph(); // Update the graph in real-time
                    })
                    .catch((error) => {
                        console.error('Error fetching status:', error);
                    });
            }, 1000); // Poll every 1 second
        })
        .catch((error) => {
            console.error('Error:', error);
        });
});

// Stop exercise
document.getElementById('stop-button').addEventListener('click', function () {
    fetch('/stop_exercise', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ total_reps: totalReps }) // Send total reps to the server
    })
        .then(response => response.json())
        .then(data => {
            console.log('Exercise stopped:', data);
            document.getElementById('exercise-interface').style.display = 'none';
            document.getElementById('my-workouts').style.display = 'block'; // Show workouts section
            // Update graph after stopping exercise
            renderWorkoutGraph();
        })
        .catch((error) => {
            console.error('Error stopping exercise:', error);
        });
});

function renderWorkoutGraph() {
    const ctx = document.getElementById('workoutGraph').getContext('2d');
    if (window.workoutChart instanceof Chart) {
        window.workoutChart.destroy(); // Destroy any previous chart instance to avoid overlaps
    }

    // Sample workout data, replace with your actual data
    workoutData = [
        { date: '2024-11-01', totalReps: 10 },
        { date: '2024-11-02', totalReps: 13 },
        { date: '2024-11-03', totalReps: 20 },
        { date: '2024-11-04', totalReps: 25 },
        { date:'2024-11-05',  totalReps:20}
    ];

    // Creating the bar chart with customized bar width and padding
    window.workoutChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: workoutData.map(entry => entry.date), // Dates as labels on X-axis
            datasets: [{
                label: 'Total Biceps Reps',
                data: workoutData.map(entry => entry.totalReps), // Rep counts on Y-axis
                backgroundColor: 'rgba(75, 192, 192, 0.7)', // Semi-transparent fill color for bars
                borderColor: 'rgba(75, 192, 192, 1)', // Outline color for bars
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Date'
                    },
                    barPercentage: 0.4,      // Adjust width of individual bars
                    categoryPercentage: 0.6, // Adjust spacing between bars
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Number of Biceps Reps'
                    }
                }
            },
            layout: {
                padding: {
                    left: 10,
                    right: 10,
                    top: 10,
                    bottom: 10
                }
            }
        }
    });
}



// Load previous workout data on page load
window.onload = loadWorkoutData;
