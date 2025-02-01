const express = require('express');
const app = express();
const mongoose = require('mongoose');

mongoose.connect('mongodb://localhost:27017/exercise-tracker', { useNewUrlParser: true, useUnifiedTopology: true });

const exerciseSchema = new mongoose.Schema({
    username: String,
    exerciseData: Object
});

const Exercise = mongoose.model('Exercise', exerciseSchema);

app.use(express.json());

app.post('/save-exercise', (req, res) => {
    const { username, exerciseData } = req.body;
    const exercise = new Exercise({ username, exerciseData });
    exercise.save((err, exercise) => {
        if (err) return res.status(500).send(err);
        res.send(exercise);
    });
});

app.listen(3000, () => {
    console.log('Server listening on port 3000');
});