let bicepRange;
let alertShown = false;
let exerciseIntervalId;
let totalReps = 0;
let exerciseData = [];
let workoutData = [];

function loadWorkoutData() {
    fetch('/api/workout-data')
        .then(response => response.json())
        .then(data => {
            workoutData = data;
            renderWorkoutGraph();
        })
        .catch((error) => {
            console.error('Error loading workout data:', error);
        });
}

document.getElementById('signin-form')?.addEventListener('submit', function (e) {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    localStorage.setItem('username', username);
    localStorage.setItem('password', password);

    document.getElementById('signin-form').classList.add('hidden');
    document.getElementById('fitness-history').classList.remove('hidden');
});

document.getElementById('fetch-fitness')?.addEventListener('click', function () {
    const fitnessLevel = document.getElementById('fitness-level').value;

    switch (fitnessLevel) {
        case 'beginner': bicepRange = 5; break;
        case 'intermediate': bicepRange = 10; break;
        case 'advanced': bicepRange = 15; break;
        default: bicepRange = 0; break;
    }

    document.getElementById('fitness-level-output').textContent =
        fitnessLevel.charAt(0).toUpperCase() + fitnessLevel.slice(1);
    document.getElementById('biceps-range').textContent = bicepRange;

    document.getElementById('fitness-result').classList.remove('hidden');
    document.getElementById('start-button').classList.remove('hidden');
});

document.getElementById('start-button')?.addEventListener('click', function () {
    fetch('/start_exercise', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log('Exercise started:', data);

            document.getElementById('fitness-history').classList.add('hidden');
            document.getElementById('exercise-interface').classList.remove('hidden');
            document.getElementById('exercise-graph-container').classList.add('hidden');

            exerciseIntervalId = setInterval(() => {
                fetch('/status')
                    .then(response => response.json())
                    .then(statusData => {
                        totalReps = statusData.counter;
                        document.getElementById('total-count').textContent = `Total Reps: ${totalReps}`;
                        document.getElementById('current-stage').textContent = `Current Stage: ${statusData.stage}`;

                        if (totalReps > bicepRange) {
                            if (!alertShown) {
                                alert('Warning: You have exceeded your recommended bicep range! Consider stopping the exercise.');
                                alertShown = true;
                            }
                        } else {
                            alertShown = false;
                        }

                        const timestamp = new Date().toLocaleString();
                        exerciseData.push({ timestamp, totalReps });
                        renderGraph();
                    })
                    .catch((error) => console.error('Error fetching status:', error));
            }, 1000);
        })
        .catch((error) => console.error('Error:', error));
});

document.getElementById('stop-button')?.addEventListener('click', function () {
    clearInterval(exerciseIntervalId);

    fetch('/stop_exercise', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ total_reps: totalReps })
    })
        .then(response => response.json())
        .then(data => {
            console.log('Exercise stopped:', data);
            document.getElementById('exercise-interface').classList.add('hidden');
            document.getElementById('exercise-graph-container').classList.remove('hidden');
            loadWorkoutData();
        })
        .catch((error) => console.error('Error stopping exercise:', error));
});

function renderGraph() {
    // Optional: Live graph logic here
}

function renderWorkoutGraph() {
    const ctx = document.getElementById('workoutGraph').getContext('2d');
    if (window.workoutChart instanceof Chart) {
        window.workoutChart.destroy();
    }

    window.workoutChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: workoutData.map(entry => entry.date),
            datasets: [{
                label: 'Total Biceps Reps',
                data: workoutData.map(entry => entry.count),
                backgroundColor: 'rgba(75, 192, 192, 0.7)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            layout: {
                padding: { left: 10, right: 10, top: 10, bottom: 10 }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Date' },
                    barPercentage: 0.4,
                    categoryPercentage: 0.6
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Number of Biceps Reps' },
                    ticks: {
                        stepSize: 5,
                        maxTicksLimit: 6
                    }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: { mode: 'index', intersect: false }
            }
        }
    });
}

document.getElementById("refresh-chart-button")?.addEventListener("click", fetchAndRenderWorkoutChart);

let workoutChart = null;

function fetchAndRenderWorkoutChart() {
    fetch('/api/workout-data')
        .then(response => response.json())
        .then(data => {
            const today = new Date();
            const labels = [...Array(7)].map((_, i) => {
                const d = new Date();
                d.setDate(today.getDate() - (6 - i));
                return d.toISOString().split('T')[0];
            });

            const counts = labels.map(date => {
                const entry = data.find(e => e.date === date);
                return entry ? entry.count : 0;
            });

            const ctx = document.getElementById('workoutGraph').getContext('2d');

            if (workoutChart instanceof Chart) {
                workoutChart.destroy();
            }

            workoutChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Biceps Reps (Last 7 Days)',
                        data: counts,
                        backgroundColor: 'rgba(37, 99, 235, 0.8)',
                        borderRadius: 6,
                        maxBarThickness: 50
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    layout: {
                        padding: { top: 10, bottom: 10, left: 10, right: 10 }
                    },
                    scales: {
                        x: {
                            title: { display: true, text: 'Date' },
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Workout Reps' },
                            ticks: {
                                precision: 0,
                                stepSize: 5,
                                maxTicksLimit: 6
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    }
                }
            });

            document.getElementById('exercise-graph-container')?.classList.remove('hidden');
        })
        .catch(error => console.error('Failed to load chart data:', error));
}

// === ✅ New Code for "My Workouts" Tab Navigation ===
document.getElementById("nav-my-workouts")?.addEventListener("click", function (e) {
    e.preventDefault();

    // Hide all main sections
    document.getElementById("signin-form")?.classList.add("hidden");
    document.getElementById("fitness-history")?.classList.add("hidden");
    document.getElementById("exercise-interface")?.classList.add("hidden");

    // Show My Workouts Section
    document.getElementById("my-workouts-section")?.classList.remove("hidden");
    document.getElementById("exercise-graph-container")?.classList.remove("hidden");

    loadWorkoutData();  // Optional reloading
});

// Hide "My Workouts" section on load
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("my-workouts-section")?.classList.add("hidden");
    
});

window.onload = loadWorkoutData;
