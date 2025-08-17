let bicepRange;
let alertShown = false;
let totalReps = 0;
let exerciseData = [];
let workoutData = [];
let videoStream = null;
let captureIntervalId = null;

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

// === Camera Handling ===
async function startCamera() {
    try {
        const video = document.getElementById("videoElement");
        videoStream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = videoStream;
        await video.play();
    } catch (err) {
        console.error("Error accessing camera:", err);
        alert("Unable to access camera. Please allow camera permissions.");
    }
}

function captureFrameAndSend() {
    const video = document.getElementById("videoElement");
    if (!video.videoWidth || !video.videoHeight) return;

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL("image/jpeg");

    fetch("/process_frame", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ image: imageData })
    })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                console.warn("Process error:", data.error);
                return;
            }
            totalReps = data.counter;
            document.getElementById('total-count').textContent = `Total Reps: ${totalReps}`;
            document.getElementById('current-stage').textContent = `Current Stage: ${data.stage}`;

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
        .catch(err => console.error("Error sending frame:", err));
}

// === Start Exercise ===
document.getElementById('start-button')?.addEventListener('click', async function () {
    await startCamera();

    fetch('/start_exercise', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            console.log('Exercise started:', data);

            document.getElementById('fitness-history').classList.add('hidden');
            document.getElementById('exercise-interface').classList.remove('hidden');
            document.getElementById('exercise-graph-container').classList.add('hidden');

            // Send frames every 500ms
            captureIntervalId = setInterval(captureFrameAndSend, 500);
        })
        .catch((error) => console.error('Error starting exercise:', error));
});

// === Stop Exercise ===
document.getElementById('stop-button')?.addEventListener('click', function () {
    clearInterval(captureIntervalId);

    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
    }

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

// === Graph Rendering ===
function renderGraph() {
    // Optional: Live graph of reps can be added here
}

function renderWorkoutGraph() {
    const ctx = document.getElementById('workoutGraph').getContext('2d');
    
    // Get last 7 workout entries
    const last7Workouts = workoutData.slice(-7);

    if (window.workoutChart instanceof Chart) {
        window.workoutChart.destroy();
    }

    window.workoutChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: last7Workouts.map(entry => entry.date),
            datasets: [{
                label: 'Total Biceps Reps',
                data: last7Workouts.map(entry => entry.count),
                backgroundColor: 'rgba(75, 192, 192, 0.7)',
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false, // lets chart follow CSS height
            layout: {
                padding: { left: 15, right: 15, top: 15, bottom: 15 }
            },
            scales: {
                x: {
                    title: { display: true, text: 'Date' },
                    ticks: {
                        autoSkip: false,
                        maxRotation: 45,
                        minRotation: 30,
                        font: { size: 12 } // larger font
                    },
                    barPercentage: 0.7,
                    categoryPercentage: 0.8
                },
                y: {
                    beginAtZero: true,
                    title: { display: true, text: 'Number of Biceps Reps' },
                    ticks: {
                        stepSize: 5,
                        maxTicksLimit: 6,
                        font: { size: 12 } // larger font
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



// === Refresh Chart Button ===
function fetchAndRenderWorkoutChart() {
    fetch('/api/workout-data')
        .then(response => response.json())
        .then(data => {
            const today = new Date();

            // ✅ Force YYYY-MM-DD (no timezone issues)
            function formatDateStrict(date) {
                return date.toISOString().split("T")[0];
            }

            // Last 7 days
            const labels = [...Array(7)].map((_, i) => {
                const d = new Date();
                d.setDate(today.getDate() - (6 - i));
                return formatDateStrict(d);
            });

            const counts = labels.map(date => {
                const entry = data.find(e => e.date === date);
                return entry ? entry.count : 0;
            });

            // ✅ Highlight today's bar in green
            const backgroundColors = labels.map(date =>
                date === formatDateStrict(today)
                    ? 'rgba(34, 197, 94, 0.9)'   // 🟢 Today
                    : 'rgba(37, 99, 235, 0.8)'   // 🔵 Other days
            );

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
            backgroundColor: 'rgba(75, 192, 192, 0.6)', // ✅ Soft color
            borderRadius: 20,   // ✅ Rounded top corners
            borderSkipped: false, // ✅ Ensures both corners are rounded
            maxBarThickness: 50
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: {
            padding: { top: 20, bottom: 20, left: 20, right: 20 }
        },
        scales: {
            x: {
                grid: {
                    display: false, // ✅ No vertical grid lines
                    drawBorder: false
                },
                title: { display: true, text: 'Date' },
                ticks: {
                    maxRotation: 0,
                    minRotation: 0
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: "rgba(200, 200, 200, 0.2)", // ✅ Light horizontal lines
                    drawBorder: false
                },
                title: { display: true, text: 'Workout Reps' },
                ticks: {
                    precision: 0,
                    stepSize: 5
                }
            }
        },
        plugins: {
            legend: { display: false },
            tooltip: {
                mode: 'index',
                intersect: false,
                backgroundColor: "rgba(0,0,0,0.7)",
                titleColor: "#fff",
                bodyColor: "#fff"
            }
        }
    }
});


            document.getElementById('exercise-graph-container')?.classList.remove('hidden');
        })
        .catch(error => console.error('Failed to load chart data:', error));
}

// === "My Workouts" Tab Navigation ===
document.getElementById("nav-my-workouts")?.addEventListener("click", function (e) {
    e.preventDefault();

    document.getElementById("signin-form")?.classList.add("hidden");
    document.getElementById("fitness-history")?.classList.add("hidden");
    document.getElementById("exercise-interface")?.classList.add("hidden");

    document.getElementById("my-workouts-section")?.classList.remove("hidden");
    document.getElementById("exercise-graph-container")?.classList.remove("hidden");

    loadWorkoutData();
});

// Hide "My Workouts" section on load
document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("my-workouts-section")?.classList.add("hidden");
});

window.onload = loadWorkoutData;
