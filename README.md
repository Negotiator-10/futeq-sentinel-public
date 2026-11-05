# FutEq Sentinel

[![tests](https://github.com/Negotiator-10/futeq-sentinel-public/actions/workflows/tests.yml/badge.svg)](https://github.com/Negotiator-10/futeq-sentinel-public/actions/workflows/tests.yml)

An automated engine for NSE F&O position limits and ban periods. It rebuilds NSE's futures-equivalent open interest, MWPL utilisation and ban-period calculations (SEBI circulars 2025/79 and 2025/122, effective 1 Oct 2025) from public exchange files. It checks a synthetic prop book against entity and intraday limits and scores its ban forecasts against NSE's published ban list.

Status: in development. The first release (v0.1) is planned for 11 Nov 2026.

All positions are synthetic. Nothing here is investment advice, and no orders are sent anywhere.
