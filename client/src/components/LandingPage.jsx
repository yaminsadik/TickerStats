import React from "react";
import { useNavigate } from "react-router-dom";
import { Box, Typography, Button, TextField, Container, Grid } from "@mui/material";
import backgroundImage from "../assets/images/backgroundCard.png"; // Use your own image or remove this line
import '../App.css';


function LandingPage() {
  const [tickers, setTickers] = React.useState("");
  const navigate = useNavigate();

  const handleNavigate = () => {
    if (tickers.trim()) {
      navigate(`/dashboard?ticker=${tickers}`);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 2,
      }}
    >
      <Container maxWidth="md" sx={{ bgcolor: "rgba(255,255,255,0.9)", borderRadius: 4, p: 4 }}>
        <Grid container spacing={4} alignItems="center" justifyContent="center">
          <Grid item xs={12}>
            <Typography variant="h3" align="center" gutterBottom>
              Bulldog Financial Stats
            </Typography>
            <Typography variant="subtitle1" align="center" color="text.secondary">
              Get instant insights into any stock. Just enter tickers and compare.
            </Typography>
          </Grid>

          <Grid item xs={12} sm={9}>
            <TextField
              label="Enter tickers (e.g., AAPL, TSLA, MSFT)"
              variant="outlined"
              fullWidth
              value={tickers}
              onChange={(e) => setTickers(e.target.value.toUpperCase())}
            />
          </Grid>

          <Grid item xs={12} sm={3}>
            <Button
              variant="contained"
              color="primary"
              fullWidth
              size="large"
              onClick={handleNavigate}
            >
              Get Stats
            </Button>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
}

export default LandingPage;
